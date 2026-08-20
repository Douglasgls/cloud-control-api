import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.integrations.headscale.dto import (
    HeadscaleNodeDTO,
    HeadscaleNodeListDTO,
    HeadscaleNodeUserDTO,
    HeadscaleUserDTO,
)

from app.integrations.headscale.exceptions import HeadscaleConnectionError
from app.models.base import Base
from app.models.connection import Connection
from app.models.connection_status import ConnectionStatus
from app.models.environment import Environment
from app.models.headscale_node import HeadscaleNode as DbHeadscaleNode
from app.models.headscale_user import HeadscaleUser as DbHeadscaleUser
from app.models.published_container import PublishedContainer
from app.services.headscale.headscale_state_sync_service import HeadscaleStateSyncService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def create_sample_api_node(node_id: str = "1", user_name: str = "env_env-1", online: bool = True, ip: str = "100.64.0.1"):
    now_str = datetime.now(timezone.utc).isoformat()
    return HeadscaleNodeDTO(
        id=node_id,
        name="test-node",
        givenName="test-node",
        user=HeadscaleNodeUserDTO(id="u1", name=user_name, createdAt=now_str),
        machine_key=f"mkey_{node_id}",
        node_key=f"nkey_{node_id}",
        ipAddresses=[ip],
        online=online,
        createdAt=now_str,
        lastSeen=now_str,
    )


@pytest.mark.anyio
async def test_sync_new_node_creation(db_session):
    # Setup Env and HeadscaleUser
    env = Environment(id="env-1", user_id=1, name="Env 1", environment_token_hash="hash1")
    user = DbHeadscaleUser(id="hu-1", environment_id="env-1", headscale_user_id="u1", name="env_env-1")
    db_session.add_all([env, user])
    db_session.commit()

    mock_client = MagicMock()
    mock_client.list_nodes.return_value = HeadscaleNodeListDTO(nodes=[create_sample_api_node("10", "env_env-1", True, "100.64.0.10")])

    mock_conn_manager = MagicMock()
    mock_conn_manager.is_connected.return_value = False

    service = HeadscaleStateSyncService(db=db_session, client=mock_client, connection_manager=mock_conn_manager)
    res = await service.sync()

    assert res["created"] == 1
    assert res["total_api_nodes"] == 1

    db_node = db_session.query(DbHeadscaleNode).filter(DbHeadscaleNode.headscale_node_id == "10").first()
    assert db_node is not None
    assert db_node.online is True
    assert db_node.tailscale_ip == "100.64.0.10"
    assert db_node.headscale_user_id == "hu-1"


@pytest.mark.anyio
async def test_sync_no_changes_idempotency(db_session):
    env = Environment(id="env-1", user_id=1, name="Env 1", environment_token_hash="hash1")
    user = DbHeadscaleUser(id="hu-1", environment_id="env-1", headscale_user_id="u1", name="env_env-1")
    db_session.add_all([env, user])
    db_session.commit()

    db_node = DbHeadscaleNode(
        id="db-n1",
        headscale_node_id="10",
        headscale_user_id="hu-1",
        machine_key="mkey_10",
        node_key="nkey_10",
        hostname="test-node",
        given_name="test-node",
        tailscale_ip="100.64.0.10",
        online=True,
        registered=True,
    )
    db_session.add(db_node)
    db_session.commit()

    mock_client = MagicMock()
    mock_client.list_nodes.return_value = HeadscaleNodeListDTO(nodes=[create_sample_api_node("10", "env_env-1", True, "100.64.0.10")])

    mock_conn_manager = MagicMock()
    mock_conn_manager.is_connected.return_value = True
    mock_conn_manager.send = AsyncMock()

    service = HeadscaleStateSyncService(db=db_session, client=mock_client, connection_manager=mock_conn_manager)
    res = await service.sync()

    assert res["created"] == 0
    assert res["updated"] == 0
    assert res["events_sent"] == 0
    mock_conn_manager.send.assert_not_called()


@pytest.mark.anyio
async def test_sync_node_became_offline(db_session):
    env = Environment(id="env-1", user_id=1, name="Env 1", environment_token_hash="hash1")
    user = DbHeadscaleUser(id="hu-1", environment_id="env-1", headscale_user_id="u1", name="env_env-1")
    container = PublishedContainer(id="cont-1", environment_id="env-1", api_local_container_id="c1", container_number=1, name="c1")
    conn = Connection(id=1, public_id="pub-123", published_container_id="cont-1", access_token_id=1, headscale_preauth_key_id="k1", status=ConnectionStatus.CONNECTED)
    
    db_node = DbHeadscaleNode(
        id="db-n1",
        headscale_node_id="10",
        headscale_user_id="hu-1",
        machine_key="mkey_10",
        node_key="nkey_10",
        hostname="test-node",
        tailscale_ip="100.64.0.10",
        online=True,
        registered=True,
    )
    conn.headscale_node_id = db_node.id

    db_session.add_all([env, user, container, conn, db_node])
    db_session.commit()

    mock_client = MagicMock()
    mock_client.list_nodes.return_value = HeadscaleNodeListDTO(nodes=[create_sample_api_node("10", "env_env-1", False, "100.64.0.10")])

    mock_conn_manager = MagicMock()
    mock_conn_manager.is_connected.return_value = True
    mock_conn_manager.send = AsyncMock()

    service = HeadscaleStateSyncService(db=db_session, client=mock_client, connection_manager=mock_conn_manager)
    res = await service.sync()

    assert res["updated"] == 1
    assert res["events_sent"] == 1

    # Verify HeadscaleNode.online is False
    db_session.refresh(db_node)
    assert db_node.online is False

    # Crucial Rule: Connection.status is NOT changed to EXPIRED or altered just because HeadscaleNode went offline
    db_session.refresh(conn)
    assert conn.status == ConnectionStatus.CONNECTED

    mock_conn_manager.send.assert_called_once()
    sent_msg = mock_conn_manager.send.call_args[0][1]
    assert sent_msg.type == "node.status_changed"
    assert sent_msg.payload["environment_id"] == "env-1"


@pytest.mark.anyio
async def test_sync_environment_isolation(db_session):
    # Setup Env A and Env B
    env_a = Environment(id="env-A", user_id=1, name="Env A", environment_token_hash="hA")
    user_a = DbHeadscaleUser(id="hu-A", environment_id="env-A", headscale_user_id="uA", name="env_env-A")
    
    env_b = Environment(id="env-B", user_id=2, name="Env B", environment_token_hash="hB")
    user_b = DbHeadscaleUser(id="hu-B", environment_id="env-B", headscale_user_id="uB", name="env_env-B")

    node_a = DbHeadscaleNode(id="db-nA", headscale_node_id="100", headscale_user_id="hu-A", machine_key="mkey_100", hostname="test-node", tailscale_ip="100.64.0.100", online=True, registered=True)
    node_b = DbHeadscaleNode(id="db-nB", headscale_node_id="200", headscale_user_id="hu-B", machine_key="mkey_200", hostname="test-node", tailscale_ip="100.64.0.200", online=True, registered=True)


    db_session.add_all([env_a, user_a, env_b, user_b, node_a, node_b])
    db_session.commit()

    # Headscale API: nodeA went offline, nodeB unchanged
    mock_client = MagicMock()
    mock_client.list_nodes.return_value = HeadscaleNodeListDTO(nodes=[
        create_sample_api_node("100", "env_env-A", False, "100.64.0.100"),
        create_sample_api_node("200", "env_env-B", True, "100.64.0.200"),
    ])

    mock_conn_manager = MagicMock()
    mock_conn_manager.is_connected.side_effect = lambda env_id: env_id in ["env-A", "env-B"]
    mock_conn_manager.send = AsyncMock()

    service = HeadscaleStateSyncService(db=db_session, client=mock_client, connection_manager=mock_conn_manager)
    res = await service.sync()

    assert res["events_sent"] == 1
    mock_conn_manager.send.assert_called_once()
    call_env_id = mock_conn_manager.send.call_args[0][0]
    assert call_env_id == "env-A"


@pytest.mark.anyio
async def test_sync_headscale_unavailable_failsafe(db_session):
    user = DbHeadscaleUser(id="hu-1", environment_id="env-1", headscale_user_id="u1", name="env_env-1")
    node = DbHeadscaleNode(id="db-n1", headscale_node_id="10", headscale_user_id="hu-1", machine_key="m1", hostname="n1", online=True, registered=True)
    db_session.add_all([user, node])
    db_session.commit()

    mock_client = MagicMock()
    mock_client.list_nodes.side_effect = HeadscaleConnectionError("Headscale API Down")

    mock_conn_manager = MagicMock()

    service = HeadscaleStateSyncService(db=db_session, client=mock_client, connection_manager=mock_conn_manager)
    res = await service.sync()

    assert res["error"] is True

    # Fail-safe rule: DB state remains intact, node is NOT marked offline
    db_session.refresh(node)
    assert node.online is True


@pytest.mark.anyio
async def test_sync_pending_connection_matching(db_session):
    env = Environment(id="env-1", user_id=1, name="Env 1", environment_token_hash="hash1")
    user = DbHeadscaleUser(id="hu-1", environment_id="env-1", headscale_user_id="u1", name="env_env-1")
    container = PublishedContainer(id="cont-1", environment_id="env-1", api_local_container_id="c1", container_number=1, name="c1")
    conn = Connection(id=1, public_id="pub-999", published_container_id="cont-1", access_token_id=1, headscale_preauth_key_id="k1", status=ConnectionStatus.PENDING, headscale_node_id=None)
    
    db_session.add_all([env, user, container, conn])
    db_session.commit()

    # Headscale API returns newly registered node for env_env-1
    mock_client = MagicMock()
    mock_client.list_nodes.return_value = HeadscaleNodeListDTO(nodes=[create_sample_api_node("50", "env_env-1", True, "100.64.0.50")])

    service = HeadscaleStateSyncService(db=db_session, client=mock_client)
    res = await service.sync()

    assert res["created"] == 1
    assert res["connections_bound"] == 1

    db_session.refresh(conn)
    assert conn.headscale_node_id is not None
    
    db_node = db_session.query(DbHeadscaleNode).filter(DbHeadscaleNode.headscale_node_id == "50").first()
    assert conn.headscale_node_id == db_node.id
