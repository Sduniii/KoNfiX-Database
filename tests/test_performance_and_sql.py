import os
from pathlib import Path
from sqlalchemy.dialects import mysql, sqlite

from app.config import Settings
from app.models.device import Device
from scripts.migrate_sqlite_to_sql import migrate_sqlite_to_target


def test_settings_mysql_database_url_generation():
    s = Settings(
        DB_ENGINE="mysql",
        DB_HOST="db.netcup.example",
        DB_PORT=3306,
        DB_NAME="k12345_konfix",
        DB_USER="k12345_user",
        DB_PASSWORD="p@ss:word/123",
    )
    assert s.DATABASE_URL == (
        "mysql+pymysql://k12345_user:p%40ss%3Aword%2F123@db.netcup.example:3306/k12345_konfix?charset=utf8mb4"
    )


def test_device_yaml_content_compiles_to_mediumtext_on_mysql():
    col_type = Device.__table__.c.yaml_content.type
    mysql_sql = col_type.compile(dialect=mysql.dialect())
    sqlite_sql = col_type.compile(dialect=sqlite.dialect())
    assert "MEDIUMTEXT" in mysql_sql.upper()
    assert "TEXT" in sqlite_sql.upper()


def test_denormalized_counts_and_cached_yaml_serving(client):
    sample_yaml = """schema_version: 1
manufacturer:
  code: perfmfg
  name: Perf Manufacturer
device:
  order_number: PERF-1000
  name: Fast Device
  hardware:
    name: Fast HW
    version: "1.0"
application:
  id: perfmfg_app_1
  name: Fast App
  version: "1.0"
  mask_version: MV-07B0
parameters:
  - id: perfmfg_p-1
    name: Param 1
    type: int
    default: "1"
  - id: perfmfg_p-2
    name: Param 2
    type: text
    default: "abc"
communication_objects:
  - id: perfmfg_ko-1
    number: 1
    name: KO 1
    dpt: "1.001"
translations:
  perfmfg_p-1:
    de: Parameter Eins
    en: Parameter One
"""
    res = client.post(
        "/api/v1/upload/yaml",
        json={"yaml": sample_yaml},
    )
    assert res.status_code == 201
    data = res.json()
    edit_code = data["edit_code"]
    dev = data["devices_imported"][0]

    # Verify list_devices uses the denormalized counts
    list_res = client.get("/api/v1/devices?search=PERF-1000")
    assert list_res.status_code == 200
    items = list_res.json()["devices"]
    assert len(items) == 1
    assert items[0]["parameters_count"] == 2
    assert items[0]["com_objects_count"] == 1
    assert items[0]["translations_count"] == 2

    # Verify cached YAML endpoint
    yaml_res = client.get("/api/v1/devices/PERF-1000/yaml")
    assert yaml_res.status_code == 200
    assert "PERF-1000" in yaml_res.text

    # Verify PATCH invalidates and updates counts when re-fetched
    patch_res = client.patch(
        "/api/v1/devices/PERF-1000",
        json={"name": "Fast Device Updated"},
        headers={"X-Edit-Code": edit_code},
    )
    assert patch_res.status_code == 200
    yaml_res_after = client.get("/api/v1/devices/PERF-1000/yaml")
    assert yaml_res_after.status_code == 200
    assert "Fast Device Updated" in yaml_res_after.text


def test_migrate_sqlite_to_sql_script(tmp_path: Path):
    src_db = tmp_path / "src.db"
    dst_db = tmp_path / "dst.db"
    src_url = f"sqlite:///{src_db}"
    dst_url = f"sqlite:///{dst_db}"

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.database import Base
    from app.models import Manufacturer, Device, CommunicationObject, Parameter

    src_engine = create_engine(src_url)
    Base.metadata.create_all(bind=src_engine)
    SrcSession = sessionmaker(bind=src_engine)
    with SrcSession() as session:
        mfg = Manufacturer(knx_id="M-9999", name="MigMfg")
        session.add(mfg)
        session.flush()
        dev = Device(
            manufacturer_id=mfg.id,
            order_number="MIG-01",
            name="Migrated Device",
            yaml_content="schema_version: 1\n",
        )
        session.add(dev)
        session.flush()
        session.add(CommunicationObject(device_id=dev.id, obj_id="ko-1", number=1, name="KO 1", dpt="1.001"))
        session.add(Parameter(device_id=dev.id, param_id="p1", name="Param 1", type="int"))
        session.commit()

    migrate_sqlite_to_target(source_sqlite=src_db, target_url=dst_url)

    dst_engine = create_engine(dst_url)
    DstSession = sessionmaker(bind=dst_engine)
    with DstSession() as session:
        migrated_dev = session.query(Device).filter(Device.order_number == "MIG-01").first()
        assert migrated_dev is not None
        assert migrated_dev.name == "Migrated Device"
        assert migrated_dev.com_objects_count == 1
        assert migrated_dev.parameters_count == 1
        assert migrated_dev.translations_count == 0


def test_web_migration_page_and_auto_env_lock(client, tmp_path: Path, monkeypatch):
    import app.api.v1.migration as mig_mod
    from app.config import settings
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.database import Base
    from app.models import Manufacturer, Device, CommunicationObject, Parameter

    fake_env = tmp_path / ".env"
    src_sqlite = tmp_path / "source_konfix.db"

    # Populate a fake source SQLite DB
    src_engine = create_engine(f"sqlite:///{src_sqlite}")
    Base.metadata.create_all(bind=src_engine)
    SrcSession = sessionmaker(bind=src_engine)
    with SrcSession() as session:
        mfg = Manufacturer(knx_id="M-7777", name="WebMigMfg")
        session.add(mfg)
        session.flush()
        dev = Device(
            manufacturer_id=mfg.id,
            order_number="WEBMIG-99",
            name="Web Migrated Actuator",
            yaml_content="schema_version: 1\n",
        )
        session.add(dev)
        session.flush()
        session.add(CommunicationObject(device_id=dev.id, obj_id="ko-99", number=1, name="KO 99", dpt="1.001"))
        session.add(Parameter(device_id=dev.id, param_id="p99", name="Param 99", type="int"))
        session.commit()
    src_engine.dispose()

    from tests.conftest import TEST_DB_URL

    monkeypatch.setattr(mig_mod, "ENV_FILE_PATH", fake_env)
    monkeypatch.setattr(mig_mod, "SOURCE_SQLITE_PATH", src_sqlite)
    monkeypatch.setattr(settings, "DATABASE_URL", TEST_DB_URL)
    monkeypatch.setattr(settings, "ENABLE_DB_MIGRATION", False)

    # 1. Default (disabled): /migrate and API endpoints must return 403 Forbidden
    assert client.get("/migrate").status_code == 403
    assert client.get("/api/v1/admin/migration-status").status_code == 403
    assert client.post("/api/v1/admin/migrate", json={}).status_code == 403

    # 2. Enable via .env file (simulating user editing .env on Plesk)
    fake_env.write_text("APP_NAME=KoNfiX-Database\nENABLE_DB_MIGRATION=true\n", encoding="utf-8")

    page_res = client.get("/migrate")
    assert page_res.status_code == 200
    assert "KoNfiX-Catalog Datenbank-Migration" in page_res.text

    status_res = client.get("/api/v1/admin/migration-status")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["migration_enabled"] is True
    assert status_data["source_sqlite"]["exists"] is True
    assert status_data["source_sqlite"]["devices_count"] == 1

    # 3. Execute migration via POST /api/v1/admin/migrate
    run_res = client.post(
        "/api/v1/admin/migrate",
        json={
            "migrate_from_sqlite": True,
            "sync_relational_and_counts": True,
            "import_yaml_files": False,
            "vacuum_sqlite": True,
            "disable_flag_after_success": True,
        },
    )
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert run_data["status"] == "success"
    assert run_data["env_flag_disabled"] is True
    assert run_data["target_db"]["devices_count"] >= 1

    # 4. Verify .env file was automatically updated to ENABLE_DB_MIGRATION=false
    env_content_after = fake_env.read_text(encoding="utf-8")
    assert "ENABLE_DB_MIGRATION=false" in env_content_after
    assert "ENABLE_DB_MIGRATION=true" not in env_content_after

    # 5. Verify page and API are immediately locked (403 Forbidden)
    assert client.get("/migrate").status_code == 403
    assert client.post("/api/v1/admin/migrate", json={}).status_code == 403

    # 6. Verify migrated device is queryable in the catalog API with accurate counts
    dev_res = client.get("/api/v1/devices/WEBMIG-99")
    assert dev_res.status_code == 200
    dev_json = dev_res.json()
    assert dev_json["name"] == "Web Migrated Actuator"
    assert dev_json["com_objects_count"] == 1
    assert dev_json["parameters_count"] == 1

