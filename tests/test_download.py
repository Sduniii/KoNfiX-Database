import pytest
import yaml

def test_download_post_returns_yaml(client, sample_knxprod_bytes):
    """Verify POST /api/v1/download delivers only KoNfiX-YAML."""
    client.post(
        "/api/v1/upload",
        content=sample_knxprod_bytes,
        headers={"Content-Type": "application/octet-stream", "X-File-Name": "MDT_AKS.knxprod"}
    )

    # Download via POST with JSON body requesting order_number
    payload = {"order_number": "AKS-0816.04"}
    res = client.post("/api/v1/download", json=payload)

    assert res.status_code == 200
    assert "text/yaml" in res.headers["content-type"]
    assert "attachment" in res.headers["content-disposition"]
    assert "AKS-0816.04.yaml" in res.headers["content-disposition"]
    assert res.headers["x-konfix-order-number"] == "AKS-0816.04"

    # Verify YAML content is valid
    parsed = yaml.safe_load(res.text)
    assert parsed["konfix_version"] == "1.0"
    assert parsed["device"]["order_number"] == "AKS-0816.04"


def test_download_post_not_found(client):
    res = client.post("/api/v1/download", json={"order_number": "NON-EXISTENT-9999"})
    assert res.status_code == 404
    assert "Kein Gerät" in res.json()["detail"]


def test_download_get_returns_yaml(client, sample_knxprod_bytes):
    """Verify GET /api/v1/download/{order_number} delivers only KoNfiX-YAML."""
    client.post(
        "/api/v1/upload",
        content=sample_knxprod_bytes,
        headers={"Content-Type": "application/octet-stream", "X-File-Name": "MDT_AKS.knxprod"}
    )

    # GET download via path
    res = client.get("/api/v1/download/AKS-0816.04")
    assert res.status_code == 200
    assert "text/yaml" in res.headers["content-type"]
    assert "AKS-0816.04.yaml" in res.headers["content-disposition"]
    parsed = yaml.safe_load(res.text)
    assert parsed["device"]["order_number"] == "AKS-0816.04"

    # GET download via query parameter
    res_query = client.get("/api/v1/download?order_number=AKS-0816.04")
    assert res_query.status_code == 200
    assert "text/yaml" in res_query.headers["content-type"]


def test_download_device_with_slashes_in_order_number(client):
    """Verify devices with slashes in order number (e.g. ABB SA/S8.16.6.2) download cleanly."""
    abb_yaml = """konfix_version: '1.0'
manufacturer:
  code: abb
  name: ABB
device:
  order_number: SA/S8.16.6.2
  name: Schaltaktor 8-fach
application:
  id: abb_sas816
  name: Schalten
communication_objects: []
parameters: []
"""
    client.post("/api/v1/upload", content=abb_yaml.encode("utf-8"), headers={"Content-Type": "text/yaml"})

    # 1. Path download with slash
    res_path = client.get("/api/v1/download/SA/S8.16.6.2")
    assert res_path.status_code == 200
    assert "text/yaml" in res_path.headers["content-type"]

    # 2. Query download
    res_query = client.get("/api/v1/download?order_number=SA/S8.16.6.2")
    assert res_query.status_code == 200
    assert "text/yaml" in res_query.headers["content-type"]

    # 3. Dedicated /devices/yaml endpoint
    res_dev_yaml = client.get("/api/v1/devices/yaml?order_number=SA/S8.16.6.2")
    assert res_dev_yaml.status_code == 200
    assert "text/yaml" in res_dev_yaml.headers["content-type"]


def test_download_synthesizes_yaml_when_physical_file_missing(client):
    """Verify that a device in DB without local physical file still downloads YAML without errors."""
    from app.database import get_db
    from app.models import Device, Manufacturer
    from app.main import app

    db = next(app.dependency_overrides[get_db]()) if get_db in app.dependency_overrides else None
    if db:
        mfg = Manufacturer(code="custom", name="Custom Maker")
        db.add(mfg)
        db.flush()
        dev = Device(
            order_number="CUSTOM-001",
            name="Custom Sensor",
            manufacturer_id=mfg.id,
            yaml_content=None
        )
        db.add(dev)
        db.commit()

    res = client.get("/api/v1/download/CUSTOM-001")
    assert res.status_code == 200
    assert "text/yaml" in res.headers["content-type"]
    parsed = yaml.safe_load(res.text)
    assert parsed["device"]["order_number"] == "CUSTOM-001"
    assert parsed["manufacturer"]["code"] == "custom"
