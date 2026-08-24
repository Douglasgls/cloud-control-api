import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.dtos.environment_sync import (
    NetworkEndpointPortSnapshotDTO,
    PublishedContainerSnapshotDTO,
    PublishedTailscaleNodeSnapshotDTO,
)
from app.models.base import Base
from app.models.environment import Environment
from app.models.published_container import PublishedContainer
from app.models.user import User
from app.services.network_catalog_service import NetworkCatalogService
from app.services.network_endpoint_sync_service import NetworkEndpointSyncService

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_network_endpoint_sync_and_catalog(db_session):
    # Create test user & environment & container
    user = User(name="Test User", email="test@example.com", password_hash="hash")
    db_session.add(user)
    db_session.flush()

    env = Environment(id="env-1", name="Dev Env", user_id=user.id, environment_token_hash="hash_env")
    db_session.add(env)
    db_session.flush()

    container = PublishedContainer(
        id="ct-101",
        environment_id=env.id,
        api_local_container_id="ct-local-1",
        container_number=101,
        name="Meu App API",
        status="running",
    )
    db_session.add(container)
    db_session.commit()

    # Create Snapshot DTO
    container_dto = PublishedContainerSnapshotDTO(
        api_local_container_id="ct-local-1",
        container_number=101,
        name="Meu App API",
        hostname="meu-app-api",
        dns_name="meu-app-api.interno",
        status="running",
        ports=[
            NetworkEndpointPortSnapshotDTO(port=80, protocol="tcp"),
            NetworkEndpointPortSnapshotDTO(port=5432, protocol="tcp"),
        ],
        tailscale=PublishedTailscaleNodeSnapshotDTO(
            installed=True,
            service_running=True,
            tailscale_ip="100.64.0.15",
            online=True,
            hostname="meu-app-api",
            dns_name="meu-app-api.interno",
        ),
    )

    # Execute sync
    sync_service = NetworkEndpointSyncService(db_session)
    endpoint = sync_service.sync_container_endpoint(container.id, container_dto)
    db_session.commit()

    assert endpoint is not None
    assert endpoint.hostname == "meu-app-api"
    assert endpoint.dns_name == "meu-app-api.interno"
    assert endpoint.tailscale_ip == "100.64.0.15"
    assert endpoint.status == "online"
    assert len(endpoint.ports) == 2

    # Query catalog
    catalog_service = NetworkCatalogService(db_session)
    catalog = catalog_service.get_catalog_for_user(user.id)

    assert len(catalog.endpoints) == 1
    item = catalog.endpoints[0]
    assert item.hostname == "meu-app-api"
    assert item.fqdn == "meu-app-api.interno"
    assert item.tailscale_ip == "100.64.0.15"
    assert item.status == "online"
    assert len(item.ports) == 2
    port_numbers = {p.port for p in item.ports}
    assert port_numbers == {80, 5432}


def test_network_endpoint_idempotency_and_offline_handling(db_session):
    user = User(name="User 2", email="user2@example.com", password_hash="hash")
    db_session.add(user)
    db_session.flush()

    env = Environment(id="env-2", name="Prod Env", user_id=user.id, environment_token_hash="hash_env2")
    db_session.add(env)
    db_session.flush()

    container = PublishedContainer(
        id="ct-102",
        environment_id=env.id,
        api_local_container_id="ct-local-2",
        container_number=102,
        name="Postgres DB",
        status="running",
    )
    db_session.add(container)
    db_session.commit()

    sync_service = NetworkEndpointSyncService(db_session)

    # Initial sync online
    dto_online = PublishedContainerSnapshotDTO(
        api_local_container_id="ct-local-2",
        container_number=102,
        name="Postgres DB",
        hostname="postgres",
        dns_name="postgres.interno",
        status="running",
        ports=[NetworkEndpointPortSnapshotDTO(port=5432, protocol="tcp")],
        tailscale=PublishedTailscaleNodeSnapshotDTO(
            installed=True,
            service_running=True,
            tailscale_ip="100.64.0.16",
            online=True,
        ),
    )
    ep1 = sync_service.sync_container_endpoint(container.id, dto_online)
    db_session.commit()

    assert ep1.status == "online"

    # Secondary sync with IP change & offline tailscale
    dto_offline = PublishedContainerSnapshotDTO(
        api_local_container_id="ct-local-2",
        container_number=102,
        name="Postgres DB",
        hostname="postgres",
        dns_name="postgres.interno",
        status="stopped",
        ports=[NetworkEndpointPortSnapshotDTO(port=5432, protocol="tcp")],
        tailscale=PublishedTailscaleNodeSnapshotDTO(
            installed=True,
            service_running=True,
            tailscale_ip="100.64.0.26",
            online=False,
        ),
    )
    ep2 = sync_service.sync_container_endpoint(container.id, dto_offline)
    db_session.commit()

    # Verify endpoint is NOT deleted, status becomes offline, IP updated
    assert ep2.id == ep1.id
    assert ep2.status == "offline"
    assert ep2.tailscale_ip == "100.64.0.26"
    assert ep2.dns_name == "postgres.interno"
