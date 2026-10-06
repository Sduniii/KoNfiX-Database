import pytest

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
