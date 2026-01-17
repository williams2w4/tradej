try:  # pragma: no cover - executed depending on SQLAlchemy version
    from sqlalchemy.orm import DeclarativeBase
except ImportError:  # Fallback for environments with SQLAlchemy < 2.0
    from sqlalchemy.orm import declarative_base

    Base = declarative_base()
else:
    class Base(DeclarativeBase):
        pass
