import io
import pytest

SAMPLE_DEVICE_YAML = """konfix_version: '1.0'
manufacturer:
  code: mdttest
  name: MDT Test Technologies
  legacy_knx_id: M-0099
device:
  order_number: TST-YAML-01
  name: Test YAML Aktor 4-fach
  description: Testgerät für YAML-Upload
  hardware:
    name: TST-YAML
    version: '1.0'
    bus_current_ma: 10.0
application:
  id: mdttest_tst_yaml_v1
  name: Test Applikation
  version: '1.0'
  mask_version: MV-07B0
communication_objects:
  - number: 0
    name: Kanal A Schalten
    function: Schalten Ein/Aus
    dpt: DPT-1.001
    flags:
      communication: true
      read: false
      write: true
      transmit: false
      update: false
parameters:
  - id: p_time
    name: Verzögerung
    type: number
    default: 5
"""

def test_yaml_upload_raw_body(client):
    """Test POST /api/v1/upload/yaml with raw YAML body in request."""
    response = client.post(
        "/api/v1/upload/yaml",
        content=SAMPLE_DEVICE_YAML,
        headers={"Content-Type": "text/yaml; charset=utf-8"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert data["manufacturer_id"] == "M-0099"
    assert len(data["devices_imported"]) == 1
    imported = data["devices_imported"][0]
    assert imported["order_number"] == "TST-YAML-01"
    assert imported["name"] == "Test YAML Aktor 4-fach"
    assert "edit_code" in imported and imported["edit_code"] is not None
    assert "edit_code" in data and data["edit_code"] is not None
    assert len(data["edit_code"]) >= 8

def test_yaml_upload_json_body(client):
    """Test POST /api/v1/upload/yaml with JSON payload {"yaml": "..."}."""
    order_no = "TST-YAML-JSON-02"
    custom_yaml = SAMPLE_DEVICE_YAML.replace("TST-YAML-01", order_no)
    response = client.post(
        "/api/v1/upload/yaml",
        json={"yaml": custom_yaml}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert data["devices_imported"][0]["order_number"] == order_no
    assert data["edit_code"] is not None

def test_yaml_upload_multipart_form(client):
    """Test POST /api/v1/upload/yaml with multipart/form-data upload."""
    order_no = "TST-YAML-FORM-03"
    custom_yaml = SAMPLE_DEVICE_YAML.replace("TST-YAML-01", order_no)
    files = {
        "file": ("device.yaml", io.BytesIO(custom_yaml.encode("utf-8")), "text/yaml")
    }
    response = client.post("/api/v1/upload/yaml", files=files)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert data["devices_imported"][0]["order_number"] == order_no
    assert data["edit_code"] is not None

def test_yaml_upload_invalid_yaml(client):
    """Test POST /api/v1/upload/yaml with malformed YAML syntax."""
    response = client.post(
        "/api/v1/upload/yaml",
        content="invalid: [yaml: broken : syntax",
        headers={"Content-Type": "text/yaml"}
    )
    assert response.status_code == 422
    assert "Ungültiges YAML-Format" in response.json()["detail"]

def test_yaml_upload_missing_fields(client):
    """Test POST /api/v1/upload/yaml with missing device fields."""
    incomplete = "konfix_version: '1.0'\nmanufacturer:\n  name: Test\n"
    response = client.post(
        "/api/v1/upload/yaml",
        content=incomplete,
        headers={"Content-Type": "text/yaml"}
    )
    assert response.status_code == 422
    assert "zwingend erforderlich" in response.json()["detail"]
