from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.dtos.client_connection import ClientConnectionConfirmRequestDTO, ValidationCode
from app.models.base import Base
from app.models.connection import Connection
from app.models.connection_status import ConnectionStatus
from app.services.client_connection_confirm_service import ClientConnectionConfirmService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_confirm_valid_uuid(db_session):
    conn_public_id = str(uuid4())
    conn = Connection(
        id=10,
        public_id=conn_public_id,
        published_container_id="cont-1",
        access_token_id=1,
        headscale_preauth_key_id="k1",
        status=ConnectionStatus.PENDING,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db_session.add(conn)
    db_session.commit()

    service = ClientConnectionConfirmService(db_session)
    req = ClientConnectionConfirmRequestDTO(connection_id=conn_public_id)
    res = service.confirm(req)

    assert res.success is True
    assert res.connection_id == conn_public_id
    assert res.status == ConnectionStatus.CONNECTED

    db_session.refresh(conn)
    assert conn.status == ConnectionStatus.CONNECTED
    assert conn.connected_at is not None


def test_confirm_invalid_uuid_returns_404(db_session):
    service = ClientConnectionConfirmService(db_session)
    req = ClientConnectionConfirmRequestDTO(connection_id=str(uuid4()))
    res = service.confirm(req)

    assert res.success is False
    assert res.code == ValidationCode.CONNECTION_NOT_FOUND


def test_confirm_enumeration_prevention(db_session):
    conn_public_id = str(uuid4())
    conn = Connection(
        id=42,
        public_id=conn_public_id,
        published_container_id="cont-1",
        access_token_id=1,
        headscale_preauth_key_id="k1",
        status=ConnectionStatus.PENDING,
    )
    db_session.add(conn)
    db_session.commit()

    service = ClientConnectionConfirmService(db_session)
    # Attempting to guess integer "42" as string fails because public_id is UUID
    req = ClientConnectionConfirmRequestDTO(connection_id="42")
    res = service.confirm(req)

    assert res.success is False
    assert res.code == ValidationCode.CONNECTION_NOT_FOUND


def test_confirm_revoked_or_expired_connection(db_session):
    conn_revoked = Connection(
        id=1,
        public_id=str(uuid4()),
        published_container_id="cont-1",
        access_token_id=1,
        headscale_preauth_key_id="k1",
        status=ConnectionStatus.REVOKED,
    )
    db_session.add(conn_revoked)
    db_session.commit()

    service = ClientConnectionConfirmService(db_session)
    req = ClientConnectionConfirmRequestDTO(connection_id=conn_revoked.public_id)
    res = service.confirm(req)

    assert res.success is False
    assert res.code == ValidationCode.CONNECTION_EXPIRED
