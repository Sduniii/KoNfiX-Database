import io
import zipfile
import pytest
import yaml

from scripts.create_sample_knxprod import create_sample_knxprod_archive


SAMPLE_KONFIX_YAML = """konfix_version: '1.0'
manufacturer:
  code: openknx
  name: OpenKNX Community
  legacy_knx_id: M-00FA
device:
  order_number: OFM-BME280-01
  name: OpenKNX Multisensor BME280
  description: DIY Umweltsensor (Temperatur, Feuchte, Luftdruck)
  hardware:
    name: OFM-BME280
    version: '1.2'
    bus_current_ma: 6.5
application:
  id: openknx_ofm_bme280
  name: BME280 Applikation
  version: '2.0'
  mask_version: MV-07B0
communication_objects:
  - number: 0
    name: Temperatur Messwert
    function: Senden
    dpt: DPT-9.001
    size: 2 Bytes
    flags:
      communication: true
      read: true
      write: false
      transmit: true
      update: false
  - number: 1
    name: Luftfeuchte Messwert
    function: Senden
    dpt: DPT-9.007
    size: 2 Bytes
    flags:
      communication: true
      read: true
      write: false
      transmit: true
      update: false
parameters:
  - id: param_cycle_temp
    name: Sendezyklus Temperatur (Sekunden)
    type: number
    default: 60
  - id: param_temp_offset
    name: Temperatur Offset
    type: number
    default: 0
"""


def test_native_yaml_upload(client):
    """Test uploading a native KoNfiX-YAML device definition."""
    headers = {
        "Content-Type": "text/yaml",
        "X-File-Name": "OFM-BME280-01.yaml"
    }

    res = client.post("/api/v1/upload", content=SAMPLE_KONFIX_YAML.encode("utf-8"), headers=headers)
    assert res.status_code == 201

    data = res.json()
    assert data["status"] == "success"
    assert data["manufacturer_code"] == "openknx"
    assert data["manufacturer_name"] == "OpenKNX Community"
    assert len(data["devices_imported"]) == 1
    assert data["devices_imported"][0]["order_number"] == "OFM-BME280-01"

    # Query device from catalog
    dev_res = client.get("/api/v1/devices/OFM-BME280-01")
    assert dev_res.status_code == 200
    dev_data = dev_res.json()
    assert dev_data["name"] == "OpenKNX Multisensor BME280"
    assert dev_data["manufacturer"]["code"] == "openknx"
    assert dev_data["yaml_url"] == "/api/v1/devices/OFM-BME280-01/yaml"

    # Fetch YAML directly
    yaml_res = client.get("/api/v1/devices/OFM-BME280-01/yaml")
    assert yaml_res.status_code == 200
    assert "text/yaml" in yaml_res.headers["content-type"]
    parsed_yaml = yaml.safe_load(yaml_res.text)
    assert parsed_yaml["manufacturer"]["code"] == "openknx"
    assert len(parsed_yaml["communication_objects"]) == 2
    assert len(parsed_yaml["parameters"]) == 2


def test_knxprod_automatic_conversion_to_yaml(client, sample_knxprod_bytes):
    """Verify that uploading a legacy .knxprod automatically generates a complete KoNfiX-YAML definition."""
    headers = {
        "Content-Type": "application/octet-stream",
        "X-File-Name": "mdt_switch_actor.knxprod"
    }

    res = client.post("/api/v1/upload", content=sample_knxprod_bytes, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "success"
    assert data["manufacturer_code"] == "mdt"

    # Device order number from sample knxprod is AKS-0816.04
    order_no = data["devices_imported"][0]["order_number"]

    # Verify YAML endpoint serves converted definition
    yaml_res = client.get(f"/api/v1/devices/{order_no}/yaml")
    assert yaml_res.status_code == 200
    assert "text/yaml" in yaml_res.headers["content-type"]

    converted = yaml.safe_load(yaml_res.text)
    assert converted["konfix_version"] == "1.0"
    assert converted["manufacturer"]["code"] == "mdt"
    assert converted["device"]["order_number"] == order_no
    assert "communication_objects" in converted
    assert "parameters" in converted


def test_zip_containing_yaml_files(client):
    """Verify uploading a ZIP archive containing native .yaml files."""
    custom_yaml = """konfix_version: '1.0'
manufacturer:
  code: diy-hacker
  name: DIY Maker Space
device:
  order_number: DIY-RELAY-4CH
  name: 4-Kanal ESP32 Relais
  hardware:
    name: ESP32-Relay
    bus_current_ma: 5.0
application:
  id: diy_relay_app
  name: Relais Steuerung
communication_objects:
  - number: 1
    name: Relais 1 Schalten
    dpt: DPT-1.001
parameters: []
"""
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("ofm_sensor.yaml", SAMPLE_KONFIX_YAML)
        zf.writestr("subfolder/diy_relay.yaml", custom_yaml)
    zip_bytes = zip_buf.getvalue()

    headers = {
        "Content-Type": "application/octet-stream",
        "X-File-Name": "open_devices.zip"
    }
    res = client.post("/api/v1/upload", content=zip_bytes, headers=headers)
    assert res.status_code == 201
    batch_data = res.json()
    assert batch_data["total_files"] == 2
    assert batch_data["successful_count"] == 2
    assert batch_data["failed_count"] == 0

    # Check that both devices are now present and queryable
    dev1 = client.get("/api/v1/devices/OFM-BME280-01")
    assert dev1.status_code == 200
    dev2 = client.get("/api/v1/devices/DIY-RELAY-4CH")
    assert dev2.status_code == 200
    assert dev2.json()["manufacturer"]["code"] == "diy-hacker"


def test_order_number_with_slashes_yaml_viewer(client):
    """Verify that devices with slashes in order numbers (e.g. ABB SA/S8.16.6.2) work with YAML endpoints."""
    abb_yaml = """konfix_version: '1.0'
manufacturer:
  code: abb
  name: ABB Stotz-Kontakt
device:
  order_number: SA/S8.16.6.2
  name: 8-fach Schaltaktor C-Last
application:
  id: abb_sas816
  name: Schalten 8f
communication_objects:
  - number: 1
    name: Kanal A Schalten
    dpt: DPT-1.001
parameters: []
"""
    up_res = client.post("/api/v1/upload", content=abb_yaml.encode("utf-8"), headers={"Content-Type": "text/yaml"})
    assert up_res.status_code == 201

    # 1. Query endpoint
    res_query = client.get("/api/v1/devices/yaml?order_number=SA/S8.16.6.2")
    assert res_query.status_code == 200
    assert "text/yaml" in res_query.headers["content-type"]
    parsed = yaml.safe_load(res_query.text)
    assert parsed["device"]["order_number"] == "SA/S8.16.6.2"

    # 2. Path endpoint
    res_path = client.get("/api/v1/devices/SA/S8.16.6.2/yaml")
    assert res_path.status_code == 200
    assert "text/yaml" in res_path.headers["content-type"]


def test_database_backfill_legacy_devices():
    """Verify that _backfill_device_yaml_specifications automatically populates yaml_content for legacy devices."""
    from app.database import get_db, _backfill_device_yaml_specifications
    from app.models import Device, Manufacturer, ApplicationProgram
    from app.main import app

    db = next(app.dependency_overrides[get_db]()) if get_db in app.dependency_overrides else None
    if db:
        mfg = Manufacturer(code="gira", name="Gira Giersiepen", knx_id="M-0008")
        db.add(mfg)
        db.flush()

        dev = Device(
            order_number="GIRA-2168-00",
            name="Tastsensor 4 Komfort",
            manufacturer_id=mfg.id,
            yaml_content=None,
            knxprod_file_id=None
        )
        db.add(dev)
        db.flush()

        app_rec = ApplicationProgram(
            device_id=dev.id,
            name="Tasten 4-fach",
            app_id="gira_app_2168",
            version="1.0"
        )
        db.add(app_rec)
        db.commit()

        # Run backfill
        _backfill_device_yaml_specifications()

        # Check that yaml_content was populated
        db.refresh(dev)
        assert dev.yaml_content is not None
        assert "GIRA-2168-00" in dev.yaml_content
        assert "gira" in dev.yaml_content
        parsed = yaml.safe_load(dev.yaml_content)
        assert parsed["device"]["order_number"] == "GIRA-2168-00"

