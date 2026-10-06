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

    # Migrations: Add new columns if not present in existing SQLite DBs
    migrations = [
        "ALTER TABLE knxprod_files ADD COLUMN source_url VARCHAR(1024)",
        "ALTER TABLE manufacturers ADD COLUMN code VARCHAR(64)",
        "ALTER TABLE devices ADD COLUMN yaml_content TEXT"
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass

    # Self-healing: Backfill yaml_content for legacy records
    _backfill_device_yaml_specifications()


def _backfill_device_yaml_specifications():
    """
    Backfills yaml_content for any existing Device in the DB that has yaml_content == None.
    Uses attached knxprod file if present on disk, otherwise synthesizes KoNfiX-YAML from DB records.
    """
    from app.models import Device, Manufacturer, ApplicationProgram, KnxprodFile
    from app.services.yaml_converter import build_konfix_yaml, generate_manufacturer_code
    from app.services.knxprod_parser import parse_knxprod_bytes
    from app.services.storage import storage_service

    db = SessionLocal()
    try:
        devices_to_backfill = db.query(Device).filter(Device.yaml_content == None).all()
        if not devices_to_backfill:
            return

        for dev in devices_to_backfill:
            yaml_content = None
            # 1. Try extracting from local physical knxprod if file exists
            if dev.knxprod_file and dev.knxprod_file.storage_path:
                try:
                    file_path = storage_service.get_file_path(dev.knxprod_file.storage_path)
                    if file_path.exists():
                        parsed = parse_knxprod_bytes(file_path.read_bytes())
                        for pd in parsed.devices:
                            if pd.order_number.strip().lower() == dev.order_number.strip().lower():
                                yaml_content = pd.yaml_content
                                break
                except Exception:
                    pass

            # 2. Fallback: synthesize from DB records
            if not yaml_content:
                mfg = dev.manufacturer
                mfg_name = mfg.name if mfg else "Unbekannter Hersteller"
                mfg_code = (mfg.code if mfg else None) or generate_manufacturer_code(mfg_name, mfg.knx_id if mfg else None)
                if mfg and not mfg.code:
                    mfg.code = mfg_code

                app0 = dev.applications[0] if dev.applications else None
                yaml_content = build_konfix_yaml(
                    manufacturer_code=mfg_code,
                    manufacturer_name=mfg_name,
                    legacy_knx_id=mfg.knx_id if mfg else None,
                    order_number=dev.order_number,
                    device_name=dev.name,
                    description=dev.description,
                    hardware_name=dev.hardware_name,
                    hardware_version=dev.hardware_version,
                    bus_current_ma=dev.bus_current_ma,
                    application_id=app0.app_id if app0 else None,
                    application_name=app0.name if app0 else None,
                    application_version=app0.version if app0 else None,
                    mask_version=app0.mask_version if app0 else None,
                    source_url=dev.knxprod_file.source_url if dev.knxprod_file else None,
                )

            dev.yaml_content = yaml_content
            # Also save file in catalog_files
            try:
                storage_service.save_yaml_content(yaml_content, f"{dev.order_number}.yaml")
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

