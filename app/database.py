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
    inklusive aller relationalen Tabellen bereitsteht.
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
            if "devices" not in tables or "parameters" not in tables:
                needs_init = True
        except Exception:
            needs_init = True

    if needs_init:
        try:
            engine.dispose()
        except Exception:
            pass

    # Ensure all tables exist
    from app.models import (  # noqa: F401
        Manufacturer,
        Device,
        ApplicationProgram,
        CommunicationObject,
        Parameter,
        AssignRule,
        Translation,
    )
    Base.metadata.create_all(bind=engine)

    # Migrations for existing databases
    migrations = [
        "ALTER TABLE devices ADD COLUMN source_url VARCHAR(1024)",
        "ALTER TABLE manufacturers ADD COLUMN code VARCHAR(64)",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass

    # Self-healing: Migriere ggf. bestehende Geräte mit yaml_content in relationale Tabellen
    _migrate_devices_to_relational()


def _migrate_devices_to_relational():
    """
    Falls Geräte in der DB existieren, deren Parameter noch nicht in relationalen
    Tabellen liegen, werden diese aus yaml_content extrahiert und relational abgelegt.
    """
    from app.models import Device, Parameter, CommunicationObject, AssignRule, Translation
    from app.services.yaml_converter import parse_konfix_yaml

    db = SessionLocal()
    try:
        devices = db.query(Device).all()
        for dev in devices:
            # Wenn bereits relationale Parameter existieren, keine Migration nötig
            param_count = db.query(Parameter).filter(Parameter.device_id == dev.id).count()
            if param_count > 0:
                continue

            if not dev.yaml_content:
                continue

            try:
                data = parse_konfix_yaml(dev.yaml_content)
            except Exception:
                continue

            dev_data = data.get("device") or {}
            if dev_data.get("source_url") and not dev.source_url:
                dev.source_url = dev_data.get("source_url")

            # 1. Communication Objects
            for co in data.get("communication_objects") or []:
                co_rec = CommunicationObject(
                    device_id=dev.id,
                    obj_id=co.get("id") or f"{dev.order_number}_o-{co.get('number', 0)}",
                    number=co.get("number", 0),
                    name=co.get("name"),
                    function=co.get("function"),
                    dpt=co.get("dpt"),
                    size=co.get("size"),
                    flags=co.get("flags"),
                    conditions=co.get("conditions")
                )
                db.add(co_rec)

            # 2. Parameters
            for p in data.get("parameters") or []:
                p_rec = Parameter(
                    device_id=dev.id,
                    param_id=p.get("id") or f"{dev.order_number}_p-{len(dev.parameters)}",
                    name=p.get("name") or "",
                    text=p.get("text"),
                    type=p.get("type"),
                    default_value=str(p.get("default")) if p.get("default") is not None else None,
                    page=p.get("page"),
                    section=p.get("section"),
                    options=p.get("options"),
                    conditions=p.get("conditions")
                )
                db.add(p_rec)

            # 3. Assign Rules
            for ar in data.get("assign_rules") or []:
                ar_rec = AssignRule(
                    device_id=dev.id,
                    target=ar.get("target"),
                    source=ar.get("source"),
                    value=ar.get("value"),
                    conditions=ar.get("conditions")
                )
                db.add(ar_rec)

            # 4. Translations
            tr_dict = data.get("translations") or {}
            for entity_id, lang_dict in tr_dict.items():
                if isinstance(lang_dict, dict):
                    for lang, text_val in lang_dict.items():
                        tr_rec = Translation(
                            device_id=dev.id,
                            entity_id=entity_id,
                            language=lang,
                            text=str(text_val)
                        )
                        db.add(tr_rec)

            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _backfill_device_yaml_specifications():
    """
    Backfills relational tables and yaml_content for legacy devices.
    """
    from app.services.yaml_converter import device_to_konfix_yaml
    from app.services.storage import storage_service

    _migrate_devices_to_relational()

    db = SessionLocal()
    try:
        devices = db.query(Device).filter(Device.yaml_content == None).all()
        for dev in devices:
            dev.yaml_content = device_to_konfix_yaml(dev)
            try:
                storage_service.save_yaml_content(dev.yaml_content, f"{dev.order_number}.yaml")
            except Exception:
                pass
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def get_db():
    ensure_database_ready()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
