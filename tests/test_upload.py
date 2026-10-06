import io
import zipfile
import pytest

from scripts.create_sample_knxprod import create_sample_knxprod_archive

def test_upload_raw_octet_stream(client, sample_knxprod_bytes):
    # Manufacturer uploads raw binary bytes with Content-Type: application/octet-stream
    headers = {
        "Content-Type": "application/octet-stream",
        "X-File-Name": "MDT_AKS_081604.knxprod"
    }

    response = client.post("/api/v1/upload", content=sample_knxprod_bytes, headers=headers)
    assert response.status_code == 201

    data = response.json()
    assert data["status"] == "success"
    assert data["manufacturer_id"] == "M-00C5"
    assert data["manufacturer_name"] == "MDT technologies"
    assert data["filename"] == "MDT_AKS_081604.knxprod"
    assert len(data["devices_imported"]) == 1
    assert data["devices_imported"][0]["order_number"] == "AKS-0816.04"

def test_upload_corrupt_data(client):
    headers = {
        "Content-Type": "application/octet-stream",
        "X-File-Name": "corrupt.knxprod"
    }
    response = client.post("/api/v1/upload", content=b"invalid raw bytes", headers=headers)
    assert response.status_code == 422
    assert "Fehler bei der KNXProd-Verarbeitung" in response.json()["detail"]

def test_upload_empty_body(client):
    headers = {"Content-Type": "application/octet-stream"}
    response = client.post("/api/v1/upload", content=b"", headers=headers)
    assert response.status_code == 400

def test_upload_zip_with_multiple_knxprods(client):
    # Create two sample knxprod files
    knxprod_mdt = create_sample_knxprod_archive(
        mfg_id="M-00C5",
        mfg_name="MDT technologies",
        order_number="AKS-0816.04",
        product_name="Schaltaktor 8-fach",
        hardware_name="AKS",
        app_name="Schalten 8f",
        app_version="1.0"
    )
    knxprod_abb = create_sample_knxprod_archive(
        mfg_id="M-0002",
        mfg_name="ABB",
        order_number="SA/S8.16.6.2",
        product_name="Schaltaktor 8-fach C-Last",
        hardware_name="SA/S",
        app_name="Schalten 8f C-Last",
        app_version="2.0"
    )

    # Package them inside a ZIP file (including one in a subfolder)
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mdt_aks.knxprod", knxprod_mdt)
        zf.writestr("subfolder/abb_sas.knxprod", knxprod_abb)
        zf.writestr("info.txt", "Some info")
    zip_bytes = zip_buf.getvalue()

    headers = {
        "Content-Type": "application/octet-stream",
        "X-File-Name": "catalog.zip"
    }
    response = client.post("/api/v1/upload", content=zip_bytes, headers=headers)
    assert response.status_code == 201

    data = response.json()
    assert data["status"] == "success"
    assert data["total_files"] == 2
    assert data["successful_count"] == 2
    assert data["failed_count"] == 0
    assert len(data["results"]) == 2

    # Check imported devices via GET /api/v1/devices
    dev_res = client.get("/api/v1/devices")
    assert dev_res.status_code == 200
    orders = [d["order_number"] for d in dev_res.json()["devices"]]
    assert "AKS-0816.04" in orders
    assert "SA/S8.16.6.2" in orders

def test_upload_batch_multipart(client):
    knxprod_1 = create_sample_knxprod_archive(
        mfg_id="M-0077",
        mfg_name="Theben AG",
        order_number="RMG 8 S KNX",
        product_name="Schaltaktor Grundmodul",
        hardware_name="RMG",
        app_name="Schalten RMG",
        app_version="3.0"
    )
    knxprod_2 = create_sample_knxprod_archive(
        mfg_id="M-0083",
        mfg_name="Gira",
        order_number="216800",
        product_name="Dimmaktor 4-fach",
        hardware_name="Dimmer",
        app_name="Dimmen 4f",
        app_version="1.3"
    )

    files = [
        ("files", ("theben.knxprod", knxprod_1, "application/octet-stream")),
        ("files", ("gira.knxprod", knxprod_2, "application/octet-stream")),
    ]
    response = client.post("/api/v1/upload/batch", files=files)
    assert response.status_code == 201

    data = response.json()
    assert data["status"] == "success"
    assert data["successful_count"] == 2
    assert data["failed_count"] == 0

def test_upload_zip_partial_failure(client, sample_knxprod_bytes):
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("valid.knxprod", sample_knxprod_bytes)
        zf.writestr("corrupted.knxprod", b"corrupted binary data not a zip")
    zip_bytes = zip_buf.getvalue()

    headers = {
        "Content-Type": "application/octet-stream",
        "X-File-Name": "mixed.zip"
    }
    response = client.post("/api/v1/upload", content=zip_bytes, headers=headers)
    assert response.status_code == 201

    data = response.json()
    assert data["status"] == "partial"
    assert data["successful_count"] == 1
    assert data["failed_count"] == 1
    assert data["results"][0]["status"] == "success"
    assert data["results"][1]["status"] == "error"

def test_upload_zip_no_knxprod(client):
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("readme.txt", "No knxprod files here")
    zip_bytes = zip_buf.getvalue()

    headers = {
        "Content-Type": "application/octet-stream",
        "X-File-Name": "empty.zip"
    }
    response = client.post("/api/v1/upload", content=zip_bytes, headers=headers)
    assert response.status_code == 422
    assert "keine gültigen .knxprod-Dateien" in response.json()["detail"]

def test_upload_batch_mixed_zip_and_knxprod(client, sample_knxprod_bytes):
    knxprod_theben = create_sample_knxprod_archive(
        mfg_id="M-0077",
        mfg_name="Theben AG",
        order_number="RMG 8 S KNX",
        product_name="Schaltaktor Grundmodul",
        hardware_name="RMG",
        app_name="Schalten RMG",
        app_version="3.0"
    )

    # 1 zip containing theben
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("theben.knxprod", knxprod_theben)
    zip_bytes = zip_buf.getvalue()

    # Upload 1 direct knxprod file + 1 zip file
    files = [
        ("files", ("mdt.knxprod", sample_knxprod_bytes, "application/octet-stream")),
        ("files", ("theben_bundle.zip", zip_bytes, "application/zip")),
    ]
    response = client.post("/api/v1/upload/batch", files=files)
    assert response.status_code == 201

    data = response.json()
    assert data["status"] == "success"
    assert data["successful_count"] == 2
    assert data["failed_count"] == 0

def test_upload_form_zip(client, sample_knxprod_bytes):
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("sample.knxprod", sample_knxprod_bytes)
    zip_bytes = zip_buf.getvalue()

    files = {"file": ("bundle.zip", zip_bytes, "application/zip")}
    response = client.post("/api/v1/upload/form", files=files)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert data["successful_count"] == 1

