from unittest.mock import patch
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.database import get_db
from app.auth.dependencies import get_current_user
from app.models.base import Base
from app.models.environment import Environment
from app.models.user import User
from app.services.environment_service import EnvironmentService


from sqlalchemy.pool import StaticPool


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_environment_service_delete_success(db_session):
    user = User(id=1, name="owner", email="owner@example.com", password_hash="hash")
    env = Environment(id="env-1", user_id=1, name="Test Env", environment_token_hash="token_hash")
    db_session.add(user)
    db_session.add(env)
    db_session.commit()

    service = EnvironmentService(db_session)
    with patch("app.services.headscale.provisioning_service.HeadscaleProvisioningService.remove_environment") as mock_remove:
        service.delete(owner=user, environment_id="env-1")
        mock_remove.assert_called_once_with("env-1")

    assert db_session.get(Environment, "env-1") is None


def test_environment_service_delete_forbidden(db_session):
    owner = User(id=1, name="owner", email="owner@example.com", password_hash="hash")
    other_user = User(id=2, name="other", email="other@example.com", password_hash="hash")
    env = Environment(id="env-1", user_id=1, name="Test Env", environment_token_hash="token_hash")
    db_session.add_all([owner, other_user, env])
    db_session.commit()

    service = EnvironmentService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        service.delete(owner=other_user, environment_id="env-1")

    assert exc_info.value.status_code == 403
    assert db_session.get(Environment, "env-1") is not None


def test_environment_service_delete_not_found(db_session):
    user = User(id=1, name="owner", email="owner@example.com", password_hash="hash")
    db_session.add(user)
    db_session.commit()

    service = EnvironmentService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        service.delete(owner=user, environment_id="env-999")

    assert exc_info.value.status_code == 404


def test_api_delete_environment_endpoint(db_session):
    user = User(id=1, name="owner", email="owner@example.com", password_hash="hash")
    env = Environment(id="env-100", user_id=1, name="API Test Env", environment_token_hash="token_hash")
    db_session.add_all([user, env])
    db_session.commit()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    client = TestClient(app)

    try:
        with patch("app.services.headscale.provisioning_service.HeadscaleProvisioningService.remove_environment"):
            response = client.delete("/api/environments/env-100")

        assert response.status_code == 204
        assert db_session.get(Environment, "env-100") is None
    finally:
        app.dependency_overrides.clear()


def test_create_environment_duplicate_name_fails(db_session):
    from app.dtos.environment import CreateEnvironmentDTO

    user = User(id=1, name="owner", email="owner@example.com", password_hash="hash")
    env = Environment(id="env-1", user_id=1, name="Proxmox", environment_token_hash="token_hash")
    db_session.add_all([user, env])
    db_session.commit()

    service = EnvironmentService(db_session)
    dto = CreateEnvironmentDTO(name="proxmox", description=None)

    with pytest.raises(HTTPException) as exc_info:
        service.create(owner=user, data=dto)

    assert exc_info.value.status_code == 400
    assert "Já existe um ambiente cadastrado com o nome" in exc_info.value.detail

