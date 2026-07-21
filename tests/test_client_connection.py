import hashlib
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import get_db
from app.dto.client_connection import (
    AuthorizedConnectionContext,
    ClientConnectionRequestDTO,
    ValidationCode,
)
from app.main import app
from app.models.access_token import AccessToken
from app.models.base import Base
from app.models.environment import Environment
from app.models.published_container import PublishedContainer
from app.models.published_node import PublishedNode
from app.models.user import User
from app.services.access_token_resolver import AccessTokenResolver
from app.services.client_connection_resolver import ClientConnectionResolver
from app.services.client_connection_service import ClientConnectionService
from app.services.container_access_authorization_service import (
    ContainerAccessAuthorizationService,
)

from sqlalchemy.pool import StaticPool

# Set up in-memory SQLite database for testing
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


@pytest.fixture(scope="function")
def client(db_session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def create_full_valid_setup(db) -> tuple[str, AccessToken, PublishedContainer, Environment, PublishedNode]:
    import uuid
    raw_token = f"valid_secret_token_{uuid.uuid4().hex}"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    user = User(name="Test User", email=f"test_{uuid.uuid4().hex}@example.com", password_hash="hash")
    db.add(user)
    db.flush()

    env = Environment(
        id="env-uuid-1234",
        user_id=user.id,
        name="Test Env",
        description="Test",
        environment_token_hash="env_hash_1234",
        status_online=True,
    )
    db.add(env)
    db.flush()

    container = PublishedContainer(
        environment_id=env.id,
        api_local_container_id="100",
        container_number=100,
        name="my-container",
        status="running",
    )
    db.add(container)
    db.flush()

    node = PublishedNode(
        published_container_id=container.id,
        installed=True,
        service_running=True,
        version="1.50.0",
        machine_id="machine-123",
        node_key="node-key-456",
        tailscale_ip="100.64.0.1",
        online=True,
    )
    db.add(node)
    db.flush()

    access_token = AccessToken(
        published_container_id=container.id,
        api_local_token_id="tok-1",
        token_hash=token_hash,
        expires_at=None,
        active=True,
    )
    db.add(access_token)
    db.commit()

    return raw_token, access_token, container, env, node


# --- UNIT TESTS: AccessTokenResolver & ClientConnectionResolver ---

def test_access_token_resolver(db_session):
    raw_token, access_token, container, env, node = create_full_valid_setup(db_session)
    resolver = AccessTokenResolver(db_session)

    token_hash, resolved = resolver.resolve(raw_token)
    assert resolved is not None
    assert resolved.id == access_token.id

    _, not_found = resolver.resolve("non_existent_token")
    assert not_found is None


def test_client_connection_resolver(db_session):
    raw_token, access_token, container, env, node = create_full_valid_setup(db_session)
    resolver = ClientConnectionResolver(db_session)

    context = resolver.resolve(raw_token)
    assert context.access_token.id == access_token.id
    assert context.published_container.id == container.id
    assert context.environment.id == env.id
    assert context.published_node.id == node.id


# --- UNIT TESTS: ContainerAccessAuthorizationService (All 11 validations) ---

def test_validation_1_token_not_found():
    service = ContainerAccessAuthorizationService()
    ctx = AuthorizedConnectionContext(raw_token="raw", token_hash="hash", access_token=None)
    result = service.authorize(ctx)
    assert result.allowed is False
    assert result.code == ValidationCode.TOKEN_NOT_FOUND


def test_validation_2_token_revoked(db_session):
    raw_token, access_token, container, env, node = create_full_valid_setup(db_session)
    access_token.active = False
    db_session.commit()

    resolver = ClientConnectionResolver(db_session)
    ctx = resolver.resolve(raw_token)
    service = ContainerAccessAuthorizationService()
    result = service.authorize(ctx)
    assert result.allowed is False
    assert result.code == ValidationCode.TOKEN_REVOKED


def test_validation_3_token_expired(db_session):
    raw_token, access_token, container, env, node = create_full_valid_setup(db_session)
    access_token.expires_at = datetime.now() - timedelta(days=1)
    db_session.commit()

    resolver = ClientConnectionResolver(db_session)
    ctx = resolver.resolve(raw_token)
    service = ContainerAccessAuthorizationService()
    result = service.authorize(ctx)
    assert result.allowed is False
    assert result.code == ValidationCode.TOKEN_EXPIRED


def test_validation_4_environment_not_found():
    service = ContainerAccessAuthorizationService()
    token = AccessToken(published_container_id=1, token_hash="h", active=True)
    ctx = AuthorizedConnectionContext(raw_token="r", token_hash="h", access_token=token, environment=None)
    result = service.authorize(ctx)
    assert result.allowed is False
    assert result.code == ValidationCode.ENVIRONMENT_NOT_FOUND


def test_validation_5_environment_offline(db_session):
    raw_token, access_token, container, env, node = create_full_valid_setup(db_session)
    env.status_online = False
    db_session.commit()

    resolver = ClientConnectionResolver(db_session)
    ctx = resolver.resolve(raw_token)
    service = ContainerAccessAuthorizationService()
    result = service.authorize(ctx)
    assert result.allowed is False
    assert result.code == ValidationCode.ENVIRONMENT_OFFLINE


def test_validation_6_container_not_found():
    service = ContainerAccessAuthorizationService()
    token = AccessToken(published_container_id=1, token_hash="h", active=True)
    env = Environment(id="env", user_id=1, name="e", environment_token_hash="h", status_online=True)
    ctx = AuthorizedConnectionContext(raw_token="r", token_hash="h", access_token=token, environment=env, published_container=None)
    result = service.authorize(ctx)
    assert result.allowed is False
    assert result.code == ValidationCode.CONTAINER_NOT_FOUND


def test_validation_7_container_offline(db_session):
    raw_token, access_token, container, env, node = create_full_valid_setup(db_session)
    container.status = "stopped"
    db_session.commit()

    resolver = ClientConnectionResolver(db_session)
    ctx = resolver.resolve(raw_token)
    service = ContainerAccessAuthorizationService()
    result = service.authorize(ctx)
    assert result.allowed is False
    assert result.code == ValidationCode.CONTAINER_OFFLINE


def test_validation_8_node_not_found(db_session):
    raw_token, access_token, container, env, node = create_full_valid_setup(db_session)
    db_session.delete(node)
    db_session.commit()

    resolver = ClientConnectionResolver(db_session)
    ctx = resolver.resolve(raw_token)
    service = ContainerAccessAuthorizationService()
    result = service.authorize(ctx)
    assert result.allowed is False
    assert result.code == ValidationCode.NODE_NOT_FOUND


def test_validation_9_tailscale_not_installed(db_session):
    raw_token, access_token, container, env, node = create_full_valid_setup(db_session)
    node.installed = False
    db_session.commit()

    resolver = ClientConnectionResolver(db_session)
    ctx = resolver.resolve(raw_token)
    service = ContainerAccessAuthorizationService()
    result = service.authorize(ctx)
    assert result.allowed is False
    assert result.code == ValidationCode.TAILSCALE_NOT_INSTALLED


def test_validation_10_tailscale_service_stopped(db_session):
    raw_token, access_token, container, env, node = create_full_valid_setup(db_session)
    node.service_running = False
    db_session.commit()

    resolver = ClientConnectionResolver(db_session)
    ctx = resolver.resolve(raw_token)
    service = ContainerAccessAuthorizationService()
    result = service.authorize(ctx)
    assert result.allowed is False
    assert result.code == ValidationCode.TAILSCALE_SERVICE_STOPPED


def test_validation_11_node_offline(db_session):
    raw_token, access_token, container, env, node = create_full_valid_setup(db_session)
    node.online = False
    db_session.commit()

    resolver = ClientConnectionResolver(db_session)
    ctx = resolver.resolve(raw_token)
    service = ContainerAccessAuthorizationService()
    result = service.authorize(ctx)
    assert result.allowed is False
    assert result.code == ValidationCode.NODE_OFFLINE


def test_validation_all_pass_success(db_session):
    raw_token, access_token, container, env, node = create_full_valid_setup(db_session)
    resolver = ClientConnectionResolver(db_session)
    ctx = resolver.resolve(raw_token)

    service = ContainerAccessAuthorizationService()
    result = service.authorize(ctx)
    assert result.allowed is True
    assert result.code is None
    assert result.context == ctx


# --- INTEGRATION TESTS: ClientConnectionService & POST /client/connect API ---

def test_api_connect_success(client, db_session):
    raw_token, _, _, _, _ = create_full_valid_setup(db_session)

    res = client.post("/client/connect", json={"access_token": raw_token})
    assert res.status_code == 200
    data = res.json()
    assert data["authorized"] is True
    assert data["code"] is None
    assert data["connection"] == {
        "login_server": None,
        "preauth_key": None,
        "hostname": None,
        "expires_at": None,
    }


def test_api_connect_token_not_found(client, db_session):
    res = client.post("/client/connect", json={"access_token": "invalid_token_999"})
    assert res.status_code == 401
    data = res.json()
    assert data["authorized"] is False
    assert data["code"] == "TOKEN_NOT_FOUND"


def test_api_connect_container_offline(client, db_session):
    raw_token, _, container, _, _ = create_full_valid_setup(db_session)
    container.status = "stopped"
    db_session.commit()

    res = client.post("/client/connect", json={"access_token": raw_token})
    assert res.status_code == 403
    data = res.json()
    assert data["authorized"] is False
    assert data["code"] == "CONTAINER_OFFLINE"
