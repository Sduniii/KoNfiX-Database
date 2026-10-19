import os
from pathlib import Path
from sqlalchemy import create_engine, func, insert, inspect, text, event
from sqlalchemy.orm import declarative_base, defer, sessionmaker

from app.config import settings


def _build_engine(db_url: str):
    if "sqlite" in db_url:
        eng = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(eng, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=10000")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return eng

    # SQL Database (MySQL / MariaDB / PostgreSQL) with connection pool health checks
    try:
        return create_engine(
            db_url,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_size=5,
            max_overflow=10,
        )
    except (ImportError, ModuleNotFoundError) as err:
        print(f"[KoNfiX DB] Warnung: Datenbank-Treiber konnte nicht geladen werden ({err}). Fallback auf lokale SQLite-Datenbank.")
        from app.config import BASE_DIR
        fallback_url = f"sqlite:///{BASE_DIR}/data/konfix_database.db"
        return _build_engine(fallback_url)


engine = _build_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

_DB_INITIALIZED: bool = False


def get_sqlite_path() -> Path | None:
    if settings.DATABASE_URL.startswith("sqlite:///") and ":memory:" not in settings.DATABASE_URL:
        raw_path = settings.DATABASE_URL.replace("sqlite:///", "")
        return Path(raw_path)
    return None


def ensure_database_ready(force: bool = False):
    """
    Self-healing check (runs once on startup or when force=True):
    Stellt sicher, dass das DB-Verzeichnis existiert und alle relationalen
    Tabellen sowie Spalten (SQLite, MySQL/MariaDB, PostgreSQL) bereitstehen.
    """
    global _DB_INITIALIZED
    db_path = get_sqlite_path()

    if _DB_INITIALIZED and not force:
        if db_path is None or (db_path.exists() and db_path.stat().st_size > 0):
            return

    needs_init = False
    if db_path:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        if not db_path.exists() or db_path.stat().st_size == 0:
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
        KnxGateway,
    )
    Base.metadata.create_all(bind=engine)

    # Idempotent column checks before issuing ALTER TABLE
    try:
        inspector = inspect(engine)
        device_cols = {c["name"] for c in inspector.get_columns("devices")}
        mfg_cols = {c["name"] for c in inspector.get_columns("manufacturers")}

        pending_migrations = []
        if "source_url" not in device_cols:
            pending_migrations.append("ALTER TABLE devices ADD COLUMN source_url VARCHAR(1024)")
        if "edit_token" not in device_cols:
            pending_migrations.append("ALTER TABLE devices ADD COLUMN edit_token VARCHAR(64)")
        if "com_objects_count" not in device_cols:
            pending_migrations.append("ALTER TABLE devices ADD COLUMN com_objects_count INTEGER NOT NULL DEFAULT 0")
        if "parameters_count" not in device_cols:
            pending_migrations.append("ALTER TABLE devices ADD COLUMN parameters_count INTEGER NOT NULL DEFAULT 0")
        if "translations_count" not in device_cols:
            pending_migrations.append("ALTER TABLE devices ADD COLUMN translations_count INTEGER NOT NULL DEFAULT 0")
        if "code" not in mfg_cols:
            pending_migrations.append("ALTER TABLE manufacturers ADD COLUMN code VARCHAR(64)")

        if pending_migrations:
            with engine.connect() as conn:
                for sql in pending_migrations:
                    try:
                        conn.execute(text(sql))
                        conn.commit()
                    except Exception:
                        pass

        # Ensure MEDIUMTEXT on MySQL/MariaDB for existing tables
        if engine.dialect.name in ("mysql", "mariadb"):
            with engine.connect() as conn:
                try:
                    conn.execute(text("ALTER TABLE devices MODIFY COLUMN yaml_content MEDIUMTEXT NULL"))
                    conn.commit()
                except Exception:
                    pass
    except Exception:
        pass

    # Self-healing: Migriere ggf. bestehende Geräte in relationale Tabellen & aktualisiere Zähler
    _migrate_devices_to_relational()
    _DB_INITIALIZED = True


def _migrate_devices_to_relational():
    """
    Falls Geräte in der DB existieren, deren Parameter noch nicht in relationalen
    Tabellen liegen oder deren Zähler-Spalten noch auf 0 stehen, werden diese
    einmalig beim Start synchronisiert.
    """
    from app.models import Device, Parameter, CommunicationObject, AssignRule, Translation
    from app.services.yaml_converter import parse_konfix_yaml

    db = SessionLocal()
    try:
        # Load devices without loading huge yaml_content unless migration is actually needed
        devices = (
            db.query(Device)
            .options(defer(Device.yaml_content))
            .filter(
                (Device.parameters_count == 0)
                & (Device.com_objects_count == 0)
                & (Device.translations_count == 0)
            )
            .all()
        )
        if not devices:
            return

        co_counts = dict(
            db.query(CommunicationObject.device_id, func.count(CommunicationObject.id))
            .group_by(CommunicationObject.device_id)
            .all()
        )
        param_counts = dict(
            db.query(Parameter.device_id, func.count(Parameter.id))
            .group_by(Parameter.device_id)
            .all()
        )
        tr_counts = dict(
            db.query(Translation.device_id, func.count(Translation.id))
            .group_by(Translation.device_id)
            .all()
        )

        dirty = False
        for dev in devices:
            c_cnt = co_counts.get(dev.id, 0)
            p_cnt = param_counts.get(dev.id, 0)
            t_cnt = tr_counts.get(dev.id, 0)

            # Wenn bereits relationale Einträge existieren, nur Zähler-Spalten synchronisieren
            if c_cnt > 0 or p_cnt > 0 or t_cnt > 0:
                dev.com_objects_count = c_cnt
                dev.parameters_count = p_cnt
                dev.translations_count = t_cnt
                dirty = True
                continue

            # Sonst einmalig aus yaml_content extrahieren (falls vorhanden)
            raw_yaml = dev.yaml_content
            if not raw_yaml:
                continue

            try:
                data = parse_konfix_yaml(raw_yaml)
            except Exception:
                continue

            dev_data = data.get("device") or {}
            if dev_data.get("source_url") and not dev.source_url:
                dev.source_url = dev_data.get("source_url")

            cos = []
            for co in data.get("communication_objects") or []:
                num = co.get("number", 0)
                cos.append({
                    "device_id": dev.id,
                    "obj_id": co.get("id") or f"{dev.order_number}_o-{num}",
                    "number": num,
                    "name": co.get("name"),
                    "function": co.get("function"),
                    "dpt": co.get("dpt"),
                    "size": co.get("size"),
                    "flags": co.get("flags"),
                    "conditions": co.get("conditions"),
                })
            if cos:
                db.execute(insert(CommunicationObject), cos)

            params = []
            for idx, p in enumerate(data.get("parameters") or []):
                params.append({
                    "device_id": dev.id,
                    "param_id": p.get("id") or f"{dev.order_number}_p-{idx + 1}",
                    "name": p.get("name") or "",
                    "text": p.get("text"),
                    "type": p.get("type"),
                    "default_value": str(p.get("default")) if p.get("default") is not None else None,
                    "page": p.get("page"),
                    "section": p.get("section"),
                    "options": p.get("options"),
                    "conditions": p.get("conditions"),
                })
            if params:
                db.execute(insert(Parameter), params)

            assigns = []
            for ar in data.get("assign_rules") or []:
                assigns.append({
                    "device_id": dev.id,
                    "target": ar.get("target"),
                    "source": ar.get("source"),
                    "value": ar.get("value"),
                    "conditions": ar.get("conditions"),
                })
            if assigns:
                db.execute(insert(AssignRule), assigns)

            trans = []
            tr_dict = data.get("translations") or {}
            for entity_id, lang_dict in tr_dict.items():
                if isinstance(lang_dict, dict):
                    for lang, text_val in lang_dict.items():
                        trans.append({
                            "device_id": dev.id,
                            "entity_id": entity_id,
                            "language": lang,
                            "text": str(text_val),
                        })
            if trans:
                for i in range(0, len(trans), 5000):
                    db.execute(insert(Translation), trans[i:i + 5000])

            dev.com_objects_count = len(cos)
            dev.parameters_count = len(params)
            dev.translations_count = len(trans)
            dirty = True

        if dirty:
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _backfill_device_yaml_specifications():
    """
    Backfills relational tables and yaml_content for legacy devices.
    """
    from app.models import Device
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
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

