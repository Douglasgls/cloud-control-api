from datetime import datetime, timezone
from unittest.mock import MagicMock
import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.environment import Environment
from app.models.published_container import PublishedContainer
from app.models.headscale_user import HeadscaleUser as DbHeadscaleUser
from app.models.headscale_preauth_key import HeadscalePreAuthKey as DbHeadscalePreAuthKey
from app.models.headscale_node import HeadscaleNode as DbHeadscaleNode

from app.integrations.headscale import (
    HeadscaleAuthenticationError,
    HeadscaleConnectionError,
    HeadscaleError,
    HeadscaleNotFoundError,
    HeadscaleRequestError,
    RestHeadscaleClient,
)
from app.services.headscale import (
    HeadscaleHealthService,
    HeadscaleNodeService,
    HeadscalePreAuthKeyService,
    HeadscaleProvisioningService,
    HeadscaleUserService,
)


@pytest.fixture
def mock_httpx_client():
    return MagicMock(spec=httpx.Client)


@pytest.fixture
def rest_client(mock_httpx_client):
    return RestHeadscaleClient(
        base_url="http://localhost:8080",
        api_key="hskey-api-AzYnF4rOay-x-dLFDQZr-xE-Ydcw7fo424bW0xQd313qNlLWeM6gNk_lz4Djf8LflBR52lPQyiLAm",
        timeout=5.0,
        client=mock_httpx_client,
    )


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


# --- CLIENT TESTS ---


def test_client_request_authentication_error(mock_httpx_client, rest_client):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 401
    mock_httpx_client.request.return_value = mock_response

    with pytest.raises(HeadscaleAuthenticationError):
        rest_client.list_users()


def test_client_request_not_found_error(mock_httpx_client, rest_client):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 404
    mock_response.text = "Not Found"
    mock_httpx_client.request.return_value = mock_response

    with pytest.raises(HeadscaleNotFoundError):
        rest_client.get_node("1")


def test_client_request_other_http_error(mock_httpx_client, rest_client):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_httpx_client.request.return_value = mock_response

    with pytest.raises(HeadscaleRequestError):
        rest_client.delete_node("1")


def test_client_request_connection_error(mock_httpx_client, rest_client):
    mock_httpx_client.request.side_effect = httpx.ConnectError("Connection refused")

    with pytest.raises(HeadscaleConnectionError):
        rest_client.list_users()


def test_client_create_user(mock_httpx_client, rest_client):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "user": {
            "id": "1",
            "name": "test-user",
            "createdAt": "2026-07-22T14:00:00Z",
        }
    }
    mock_httpx_client.request.return_value = mock_response

    dto = rest_client.create_user("test-user")
    assert dto.id == "1"
    assert dto.name == "test-user"
    assert dto.createdAt == "2026-07-22T14:00:00Z"

    mock_httpx_client.request.assert_called_once_with(
        "POST",
        "http://localhost:8080/api/v1/user",
        json={"name": "test-user"},
        params=None,
    )


def test_client_list_users(mock_httpx_client, rest_client):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "users": [
            {"id": "1", "name": "user-1", "createdAt": "2026-07-22T14:00:00Z"},
            {"id": "2", "name": "user-2", "createdAt": "2026-07-22T14:05:00Z"},
        ]
    }
    mock_httpx_client.request.return_value = mock_response

    dto_list = rest_client.list_users()
    assert len(dto_list.users) == 2
    assert dto_list.users[0].name == "user-1"
    assert dto_list.users[1].name == "user-2"


def test_client_get_user_success(mock_httpx_client, rest_client):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "users": [
            {"id": "1", "name": "user-1", "createdAt": "2026-07-22T14:00:00Z"},
        ]
    }
    mock_httpx_client.request.return_value = mock_response

    dto = rest_client.get_user("user-1")
    assert dto.id == "1"
    assert dto.name == "user-1"


def test_client_get_user_not_found(mock_httpx_client, rest_client):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"users": []}
    mock_httpx_client.request.return_value = mock_response

    with pytest.raises(HeadscaleNotFoundError):
        rest_client.get_user("user-1")


def test_client_delete_user(mock_httpx_client, rest_client):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_httpx_client.request.return_value = mock_response

    rest_client.delete_user("user-1")
    mock_httpx_client.request.assert_called_once_with(
        "DELETE",
        "http://localhost:8080/api/v1/user/user-1",
        json=None,
        params=None,
    )


def test_client_rename_user(mock_httpx_client, rest_client):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "user": {"id": "1", "name": "new-user", "createdAt": "2026-07-22T14:00:00Z"}
    }
    mock_httpx_client.request.return_value = mock_response

    dto = rest_client.rename_user("old-user", "new-user")
    assert dto.name == "new-user"
    mock_httpx_client.request.assert_called_once_with(
        "POST",
        "http://localhost:8080/api/v1/user/old-user/rename/new-user",
        json=None,
        params=None,
    )


def test_client_create_preauth_key(mock_httpx_client, rest_client):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "preauthKey": {
            "id": "key1",
            "user": "test-user",
            "key": "secretkeyval",
            "reusable": True,
            "ephemeral": False,
            "used": False,
            "createdAt": "2026-07-22T14:00:00Z",
            "expiration": "2026-07-22T15:00:00Z",
        }
    }
    mock_httpx_client.request.return_value = mock_response

    exp = datetime(2026, 7, 22, 15, 0, 0, tzinfo=timezone.utc)
    dto = rest_client.create_preauth_key("test-user", reusable=True, expiration=exp)
    assert dto.id == "key1"
    assert dto.key == "secretkeyval"
    assert dto.reusable is True

    mock_httpx_client.request.assert_called_once_with(
        "POST",
        "http://localhost:8080/api/v1/preauthkey",
        json={"user": "test-user", "reusable": True, "ephemeral": False, "expiration": "2026-07-22T15:00:00Z"},
        params=None,
    )


def test_client_expire_preauth_key(mock_httpx_client, rest_client):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_httpx_client.request.return_value = mock_response

    rest_client.expire_preauth_key("test-user", "mykey")
    mock_httpx_client.request.assert_called_once_with(
        "POST",
        "http://localhost:8080/api/v1/preauthkey/expire",
        json={"user": "test-user", "key": "mykey"},
        params=None,
    )


def test_client_list_nodes(mock_httpx_client, rest_client):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "nodes": [
            {
                "id": "1",
                "name": "node-1",
                "givenName": "node-1-given",
                "user": {"id": "u1", "name": "user-1", "createdAt": "2026-07-22T14:00:00Z"},
                "ipAddresses": ["100.64.0.1"],
                "online": True,
                "validTags": [],
                "forcedTags": [],
                "createdAt": "2026-07-22T14:10:00Z",
                "lastSeen": "2026-07-22T14:20:00Z",
                "expiry": "0001-01-01T00:00:00Z",
            }
        ]
    }
    mock_httpx_client.request.return_value = mock_response

    dto_list = rest_client.list_nodes(user="user-1")
    assert len(dto_list.nodes) == 1
    assert dto_list.nodes[0].name == "node-1"
    assert dto_list.nodes[0].ipAddresses == ["100.64.0.1"]

    mock_httpx_client.request.assert_called_once_with(
        "GET",
        "http://localhost:8080/api/v1/node",
        json=None,
        params={"user": "user-1"},
    )


def test_client_rename_node(mock_httpx_client, rest_client):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "node": {
            "id": "1",
            "name": "new-node-name",
            "givenName": "node-1-given",
            "user": {"id": "u1", "name": "user-1", "createdAt": "2026-07-22T14:00:00Z"},
            "ipAddresses": [],
            "online": True,
            "validTags": [],
            "forcedTags": [],
            "createdAt": "2026-07-22T14:10:00Z",
            "lastSeen": "2026-07-22T14:20:00Z",
            "expiry": "0001-01-01T00:00:00Z",
        }
    }
    mock_httpx_client.request.return_value = mock_response

    dto = rest_client.rename_node("1", "new-node-name")
    assert dto.name == "new-node-name"
    mock_httpx_client.request.assert_called_once_with(
        "POST",
        "http://localhost:8080/api/v1/node/1/rename/new-node-name",
        json=None,
        params=None,
    )


def test_client_move_node(mock_httpx_client, rest_client):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "node": {
            "id": "1",
            "name": "node-1",
            "givenName": "node-1-given",
            "user": {"id": "u2", "name": "user-2", "createdAt": "2026-07-22T14:00:00Z"},
            "ipAddresses": [],
            "online": True,
            "validTags": [],
            "forcedTags": [],
            "createdAt": "2026-07-22T14:10:00Z",
            "lastSeen": "2026-07-22T14:20:00Z",
            "expiry": "0001-01-01T00:00:00Z",
        }
    }
    mock_httpx_client.request.return_value = mock_response

    dto = rest_client.move_node("1", "user-2")
    assert dto.user.name == "user-2"
    mock_httpx_client.request.assert_called_once_with(
        "POST",
        "http://localhost:8080/api/v1/node/1/user",
        json={"user": "user-2"},
        params={"user": "user-2"},
    )


# --- SERVICE TESTS ---


def test_user_service_create_user(mock_httpx_client, db_session):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "user": {"id": "123", "name": "john", "createdAt": "2026-07-22T14:00:00Z"}
    }
    mock_httpx_client.request.return_value = mock_response

    # Setup database env
    env = Environment(id="env-1", user_id=1, name="env-1", environment_token_hash="h1", status_online=True)
    db_session.add(env)
    db_session.commit()

    client = RestHeadscaleClient("http://localhost:8080", "key", client=mock_httpx_client)
    user_service = HeadscaleUserService(db_session, client=client)

    user = user_service.create_user("env-1", "john")
    assert user.headscale_user_id == "123"
    assert user.name == "john"
    assert user.environment_id == "env-1"


def test_preauth_key_service_create(mock_httpx_client, db_session):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "preauthKey": {
            "id": "k1",
            "user": "john",
            "key": "secret",
            "reusable": False,
            "ephemeral": True,
            "used": False,
            "createdAt": "2026-07-22T14:00:00Z",
            "expiration": "2026-07-22T15:00:00Z",
        }
    }
    mock_httpx_client.request.return_value = mock_response

    # Setup database env and user
    env = Environment(id="env-1", user_id=1, name="env-1", environment_token_hash="h1", status_online=True)
    db_session.add(env)
    db_session.commit()
    db_user = DbHeadscaleUser(environment_id="env-1", headscale_user_id="123", name="john")
    db_session.add(db_user)
    db_session.commit()

    client = RestHeadscaleClient("http://localhost:8080", "key", client=mock_httpx_client)
    key_service = HeadscalePreAuthKeyService(db_session, client=client)

    key = key_service.create(headscale_user_db_id=db_user.id, user_name="john", ephemeral=True)
    assert key.headscale_key_id == "k1"
    assert key.key_name == "secret"
    assert key.ephemeral is True


def test_node_service_list(mock_httpx_client, db_session):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"nodes": []}
    mock_httpx_client.request.return_value = mock_response

    client = RestHeadscaleClient("http://localhost:8080", "key", client=mock_httpx_client)
    node_service = HeadscaleNodeService(db_session, client=client)

    nodes = node_service.list()
    assert len(nodes) == 0


def test_health_service_check_healthy(mock_httpx_client):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"users": []}
    mock_httpx_client.request.return_value = mock_response

    client = RestHeadscaleClient("http://localhost:8080", "key", client=mock_httpx_client)
    health_service = HeadscaleHealthService(client=client)

    assert health_service.check() is True


def test_health_service_check_unhealthy(mock_httpx_client):
    mock_httpx_client.request.side_effect = httpx.ConnectError("Offline")

    client = RestHeadscaleClient("http://localhost:8080", "key", client=mock_httpx_client)
    health_service = HeadscaleHealthService(client=client)

    assert health_service.check() is False


def test_provisioning_service_orchestration(mock_httpx_client, db_session):
    # Mocking responses:
    # 1. get_user (fails because user doesn't exist)
    # 2. create_user
    # 3. create_preauth_key

    mock_get_response = MagicMock(spec=httpx.Response)
    mock_get_response.status_code = 404
    mock_get_response.json.return_value = {"message": "Not found"}

    mock_create_user_response = MagicMock(spec=httpx.Response)
    mock_create_user_response.status_code = 200
    mock_create_user_response.json.return_value = {
        "user": {"id": "123", "name": "john", "createdAt": "2026-07-22T14:00:00Z"}
    }

    mock_create_key_response = MagicMock(spec=httpx.Response)
    mock_create_key_response.status_code = 200
    mock_create_key_response.json.return_value = {
        "preauthKey": {
            "id": "k1",
            "user": "john",
            "key": "secret",
            "reusable": False,
            "ephemeral": True,
            "used": False,
            "createdAt": "2026-07-22T14:00:00Z",
            "expiration": "2026-07-22T15:00:00Z",
        }
    }

    mock_httpx_client.request.side_effect = [
        mock_get_response,
        mock_create_user_response,
        mock_create_key_response,
    ]

    # Setup DB
    env = Environment(id="env-1", user_id=1, name="env-1", environment_token_hash="h1", status_online=True)
    db_session.add(env)
    db_session.commit()

    client = RestHeadscaleClient("http://localhost:8080", "key", client=mock_httpx_client)
    user_service = HeadscaleUserService(db_session, client=client)
    key_service = HeadscalePreAuthKeyService(db_session, client=client)

    provision_service = HeadscaleProvisioningService(
        db_session,
        user_service=user_service,
        preauthkey_service=key_service,
    )

    user, key = provision_service.provision_environment("env-1", "john", ephemeral=True)
    assert user.name == "john"
    assert key.key_name == "secret"
    assert mock_httpx_client.request.call_count == 3


def test_provisioning_ensure_methods(mock_httpx_client, db_session):
    # 1. Setup DB
    env = Environment(id="env-1", user_id=1, name="env-1", environment_token_hash="h1", status_online=True)
    container = PublishedContainer(id="container-1", environment_id="env-1", api_local_container_id="101", container_number=101, name="c1", status="running")
    db_session.add(env)
    db_session.add(container)
    db_session.commit()

    # Mocks
    mock_get_user = MagicMock(spec=httpx.Response)
    mock_get_user.status_code = 200
    mock_get_user.json.return_value = {"users": [{"id": "123", "name": "john", "createdAt": "2026-07-22T14:00:00Z"}]}

    mock_create_key = MagicMock(spec=httpx.Response)
    mock_create_key.status_code = 200
    mock_create_key.json.return_value = {
        "preauthKey": {
            "id": "k1",
            "user": "john",
            "key": "secret",
            "reusable": False,
            "ephemeral": True,
            "used": False,
            "createdAt": "2026-07-22T14:00:00Z",
            "expiration": "2026-07-22T15:00:00Z",
        }
    }

    mock_httpx_client.request.side_effect = [
        mock_get_user,
        mock_create_key,
    ]

    client = RestHeadscaleClient("http://localhost:8080", "key", client=mock_httpx_client)
    user_service = HeadscaleUserService(db_session, client=client)
    key_service = HeadscalePreAuthKeyService(db_session, client=client)

    provision_service = HeadscaleProvisioningService(
        db_session,
        user_service=user_service,
        preauthkey_service=key_service,
    )

    # test ensure_environment_user
    db_user = provision_service.ensure_environment_user("env-1", "john")
    assert db_user.headscale_user_id == "123"

    # test ensure_container_preauth_key (creates new key)
    db_key = provision_service.ensure_container_preauth_key(
        environment_id="env-1",
        published_container_id="container-1",
        ephemeral=True
    )
    assert db_key.headscale_key_id == "k1"
    assert db_key.key_name == "secret"

    # test ensure_container_preauth_key (uses existing active key)
    db_key_2 = provision_service.ensure_container_preauth_key(
        environment_id="env-1",
        published_container_id="container-1"
    )
    assert db_key_2.id == db_key.id
