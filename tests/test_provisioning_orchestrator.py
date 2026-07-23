from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.environment import Environment
from app.models.headscale_user import HeadscaleUser
from app.models.published_container import PublishedContainer
from app.models.provisioning_status import ProvisioningStatus
from app.services.headscale.provisioning_orchestrator import ProvisioningOrchestrator


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.mark.anyio
async def test_orchestrator_offline_agent_retains_key_created(db_session):
    # Setup test environment & container
    env = Environment(id="env-123", user_id=1, name="Env Test", environment_token_hash="hash", status_online=True)
    container = PublishedContainer(
        id="cont-123",
        environment_id="env-123",
        api_local_container_id="ct-100",
        container_number=100,
        name="CT 100",
        status="running",
        provisioning_status=ProvisioningStatus.PENDING,
    )
    db_session.add(env)
    db_session.add(container)
    db_session.commit()

    # Mock provisioning service
    mock_prov_service = MagicMock()
    mock_prov_service.ensure_environment_user.return_value = HeadscaleUser(
        id="hu-1", environment_id="env-123", headscale_user_id="api-1", name="env_env-123"
    )
    mock_key = MagicMock()
    mock_key.key_name = "hs_pk_secret123"
    mock_key.used = False
    mock_key.expiration = None
    mock_prov_service.ensure_container_preauth_key.return_value = mock_key

    # Mock connection manager (agent offline)
    mock_conn_manager = MagicMock()
    mock_conn_manager.is_connected.return_value = False

    orchestrator = ProvisioningOrchestrator(
        db=db_session,
        connection_manager=mock_conn_manager,
        provisioning_service=mock_prov_service,
    )

    result = await orchestrator.orchestrate("env-123")
    assert result == []

    # Container state must be KEY_CREATED, not WAITING_AGENT
    updated_container = db_session.query(PublishedContainer).filter_by(id="cont-123").first()
    assert updated_container.provisioning_status == ProvisioningStatus.KEY_CREATED


@pytest.mark.anyio
async def test_orchestrator_online_agent_dispatches_event(db_session):
    env = Environment(id="env-456", user_id=1, name="Env Online", environment_token_hash="hash2", status_online=True)
    container = PublishedContainer(
        id="cont-456",
        environment_id="env-456",
        api_local_container_id="ct-200",
        container_number=200,
        name="CT 200",
        status="running",
        provisioning_status=ProvisioningStatus.PENDING,
    )
    db_session.add(env)
    db_session.add(container)
    db_session.commit()

    mock_prov_service = MagicMock()
    mock_prov_service.ensure_environment_user.return_value = HeadscaleUser(
        id="hu-2", environment_id="env-456", headscale_user_id="api-2", name="env_env-456"
    )
    mock_key = MagicMock()
    mock_key.key_name = "hs_pk_secret456"
    mock_key.used = False
    mock_key.expiration = None
    mock_prov_service.ensure_container_preauth_key.return_value = mock_key

    # Mock connection manager (agent online)
    mock_conn_manager = MagicMock()
    mock_conn_manager.is_connected.return_value = True
    mock_conn_manager.send = AsyncMock()

    orchestrator = ProvisioningOrchestrator(
        db=db_session,
        connection_manager=mock_conn_manager,
        provisioning_service=mock_prov_service,
    )

    result = await orchestrator.orchestrate("env-456")
    assert result == ["cont-456"]

    # Container state must be WAITING_AGENT
    updated_container = db_session.query(PublishedContainer).filter_by(id="cont-456").first()
    assert updated_container.provisioning_status == ProvisioningStatus.WAITING_AGENT

    # Verify event payload
    mock_conn_manager.send.assert_called_once()
    args = mock_conn_manager.send.call_args[0]
    assert args[0] == "env-456"
    msg = args[1]
    assert msg.type == "container.provision"
    assert msg.payload["published_container_id"] == "cont-456"
    assert msg.payload["api_local_container_id"] == "ct-200"
    assert msg.payload["container_number"] == 200
    assert msg.payload["preauth_key"] == "hs_pk_secret456"
    assert msg.payload["headscale_user"] == "env_env-456"
