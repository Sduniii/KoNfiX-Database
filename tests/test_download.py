import pytest

def test_download_post_octet_stream(client, sample_knxprod_bytes):
    # 1. Upload device first
    client.post(
        "/api/v1/upload",
        content=sample_knxprod_bytes,
        headers={"Content-Type": "application/octet-stream", "X-File-Name": "MDT_AKS.knxprod"}
    )

    # 2. Download via POST with JSON body requesting order_number
    payload = {"order_number": "AKS-0816.04"}
    res = client.post("/api/v1/download", json=payload)

    assert res.status_code == 200
    assert res.headers["content-type"] == "application/octet-stream"
    assert "attachment" in res.headers["content-disposition"]
    assert "MDT_AKS.knxprod" in res.headers["content-disposition"]
    assert res.headers["x-knx-order-number"] == "AKS-0816.04"
    assert "x-checksum-sha256" in res.headers

    # Verify binary content matches
    assert res.content == sample_knxprod_bytes

def test_download_post_not_found(client):
    res = client.post("/api/v1/download", json={"order_number": "NON-EXISTENT-9999"})
    assert res.status_code == 404
    assert "Kein Gerät" in res.json()["detail"]

def test_download_get_octet_stream(client, sample_knxprod_bytes):
    # Upload first
    client.post(
        "/api/v1/upload",
        content=sample_knxprod_bytes,
        headers={"Content-Type": "application/octet-stream", "X-File-Name": "MDT_AKS.knxprod"}
    )

    # GET download
    res = client.get("/api/v1/download/AKS-0816.04")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/octet-stream"
    assert res.content == sample_knxprod_bytes
