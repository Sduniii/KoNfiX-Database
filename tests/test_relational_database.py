import yaml
import pytest
from app.models import (
    Device,
    Manufacturer,
    CommunicationObject,
    Parameter,
    AssignRule,
    Translation,
)
from app.database import get_db
from app.config import settings
from pathlib import Path


def test_knxprod_upload_populates_relational_tables_and_no_binary_on_disk(client, sample_knxprod_bytes):
    """
    Verify that uploading a .knxprod file:
    1. Populates relational tables (CommunicationObject, Parameter, etc.) in SQLite.
    2. Does NOT store any .knxprod file in the physical storage directory.
    3. Provides REST endpoints to query communication objects and parameters directly.
    4. Generates valid KoNfiX-YAML dynamically on-the-fly on download.
    """
    storage_dir = Path(settings.STORAGE_DIR)
    initial_knxprod_files = list(storage_dir.glob("*.knxprod"))

    res = client.post(
        "/api/v1/upload",
        content=sample_knxprod_bytes,
        headers={"Content-Type": "application/octet-stream", "X-File-Name": "test_aku.knxprod"}
    )
    assert res.status_code == 201

    # 1. No .knxprod binary written to storage directory
    current_knxprod_files = list(storage_dir.glob("*.knxprod"))
    assert len(current_knxprod_files) == len(initial_knxprod_files)

    # 2. Query relational endpoints
    res_cos = client.get("/api/v1/devices/AKS-0816.04/communication-objects")
    assert res_cos.status_code == 200
    cos = res_cos.json()
    assert len(cos) > 0
    # Verify structure of COs
    co0 = cos[0]
    assert "number" in co0
    assert "name" in co0
    assert "function" in co0
    assert "flags" in co0

    res_params = client.get("/api/v1/devices/AKS-0816.04/parameters")
    assert res_params.status_code == 200
    params = res_params.json()
    assert len(params) > 0
    param0 = params[0]
    assert "param_id" in param0
    assert "name" in param0
    assert "type" in param0

    # 3. Dynamic YAML download
    res_dl = client.get("/api/v1/download/AKS-0816.04")
    assert res_dl.status_code == 200
    assert "text/yaml" in res_dl.headers["content-type"]
    parsed_yaml = yaml.safe_load(res_dl.text)
    assert parsed_yaml["device"]["order_number"] == "AKS-0816.04"
    assert "communication_objects" in parsed_yaml
    assert len(parsed_yaml["communication_objects"]) == len(cos)


def test_granular_query_on_relational_parameters_and_cos(client, sample_knxprod_bytes):
    """Verify filtering and searching directly on relational endpoints."""
    # Ensure device is uploaded
    client.post(
        "/api/v1/upload",
        content=sample_knxprod_bytes,
        headers={"Content-Type": "application/octet-stream", "X-File-Name": "test_filter.knxprod"}
    )

    # Filter COs by search query
    res_cos_q = client.get("/api/v1/devices/AKS-0816.04/communication-objects?q=Schalten")
    assert res_cos_q.status_code == 200
    for co in res_cos_q.json():
        assert "schalten" in (co["name"] or "").lower() or "schalten" in (co["function"] or "").lower()

    # Filter parameters by type if any
    res_params = client.get("/api/v1/devices/AKS-0816.04/parameters")
    assert res_params.status_code == 200
    all_params = res_params.json()
    if any(p["type"] == "enum" for p in all_params):
        res_enum = client.get("/api/v1/devices/AKS-0816.04/parameters?param_type=enum")
        assert res_enum.status_code == 200
        for p in res_enum.json():
            assert p["type"] == "enum"
