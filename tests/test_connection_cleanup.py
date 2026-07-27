from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.connection import Connection
from app.models.connection_status import ConnectionStatus
from app.models.user import User
from app.models.environment import Environment
from app.models.published_container import PublishedContainer
from app.models.access_token import AccessToken
from app.models.headscale_user import HeadscaleUser
from app.models.headscale_preauth_key import HeadscalePreAuthKey
from app.services.connection_cleanup_service import ConnectionCleanupService

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


def test_cleanup_expired_pending_connections(db_session):
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)

    user = User(name="User", email="user@example.com", password_hash="hash")
    db_session.add(user)
    db_session.flush()

    env = Environment(id="env-cleanup", name="Env", user_id=user.id, environment_token_hash="hash_env")
    db_session.add(env)
    db_session.flush()

    container = PublishedContainer(id="ct-cleanup", name="CT", environment_id=env.id, api_local_container_id=100)
    db_session.add(container)
    db_session.flush()

    token = AccessToken(token_hash="hash_clean", published_container_id=container.id)
    db_session.add(token)
    db_session.flush()

    hs_user = HeadscaleUser(id="hu-cleanup", environment_id=env.id, headscale_user_id="hs-clean", name="env_clean")
    db_session.add(hs_user)
    db_session.flush()

    key = HeadscalePreAuthKey(id="hk-cleanup", headscale_user_id=hs_user.id, headscale_key_id="k-clean", key_name="key_clean")
    db_session.add(key)
    db_session.flush()

    # 1. Active connected connection (should NOT be expired)
    conn_active = Connection(
        published_container_id=container.id,
        access_token_id=token.id,
        headscale_preauth_key_id=key.id,
        status=ConnectionStatus.CONNECTED,
        expires_at=now_naive - timedelta(minutes=10),
    )

    # 2. PENDING connection that expired 5 minutes ago (SHOULD be expired)
    conn_pending_expired = Connection(
        published_container_id=container.id,
        access_token_id=token.id,
        headscale_preauth_key_id=key.id,
        status=ConnectionStatus.PENDING,
        expires_at=now_naive - timedelta(minutes=5),
    )

    # 3. PENDING connection valid for 5 more minutes (should NOT be expired)
    conn_pending_valid = Connection(
        published_container_id=container.id,
        access_token_id=token.id,
        headscale_preauth_key_id=key.id,
        status=ConnectionStatus.PENDING,
        expires_at=now_naive + timedelta(minutes=5),
    )

    db_session.add_all([conn_active, conn_pending_expired, conn_pending_valid])
    db_session.commit()

    cleanup_service = ConnectionCleanupService(db_session)
    cleaned_count = cleanup_service.cleanup_expired_pending_connections()

    assert cleaned_count == 1

    db_session.refresh(conn_active)
    db_session.refresh(conn_pending_expired)
    db_session.refresh(conn_pending_valid)

    assert conn_active.status == ConnectionStatus.CONNECTED
    assert conn_pending_expired.status == ConnectionStatus.EXPIRED
    assert conn_pending_valid.status == ConnectionStatus.PENDING
