import os
from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_sqlite_path() -> Path | None:
    if "sqlite:///" in settings.DATABASE_URL:
        raw_path = settings.DATABASE_URL.replace("sqlite:///", "")
        return Path(raw_path)
    return None


def ensure_database_ready():
    """
    Self-healing check:
    Stellt sicher, dass das DB-Verzeichnis existiert und die SQLite-Datei
    inklusive aller Tabellen bereitsteht – selbst wenn die Datei im laufenden
    Betrieb gelöscht wurde.
    """
    db_path = get_sqlite_path()
    needs_init = False

    if db_path:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        if not db_path.exists() or db_path.stat().st_size == 0:
            needs_init = True

    if not needs_init:
        try:
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            if "devices" not in tables:
                needs_init = True
        except Exception:
            needs_init = True

    if needs_init:
        # Import models so Base.metadata knows about all tables
        from app.models import ApplicationProgram, Device, KnxprodFile, Manufacturer  # noqa: F401
        Base.metadata.create_all(bind=engine)

        # Migration: Add source_url column if not present in legacy SQLite DBs
        try:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE knxprod_files ADD COLUMN source_url VARCHAR(1024)"))
                conn.commit()
        except Exception:
            pass


def get_db():
    ensure_database_ready()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

