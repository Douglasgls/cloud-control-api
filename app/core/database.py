from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """Fornece uma sessão SQLAlchemy por requisição."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_database_schema() -> None:
    """Inicialização local de desenvolvimento; produção deve executar migrations."""
    # Importa os modelos antes de criar o metadata, sem acoplar controllers ao banco.
    import app.models  # noqa: F401
    from app.models.base import Base

    Base.metadata.create_all(bind=engine)
