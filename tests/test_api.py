import pytest

def test_api_devices_and_manufacturers(client, sample_knxprod_bytes):
    # Upload sample device
    client.post(
        "/api/v1/upload",
        content=sample_knxprod_bytes,
        headers={"Content-Type": "application/octet-stream", "X-File-Name": "MDT_AKS.knxprod"}
    )

    # 1. Test GET /devices
    res = client.get("/api/v1/devices")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert data["devices"][0]["order_number"] == "AKS-0816.04"

    # 2. Test search with q
    res_search = client.get("/api/v1/devices?q=AKS")
    assert res_search.status_code == 200
    assert len(res_search.json()["devices"]) >= 1

    # 3. Test filter by manufacturer
    res_mfg = client.get("/api/v1/devices?manufacturer_id=M-00C5")
    assert res_mfg.status_code == 200
    assert len(res_mfg.json()["devices"]) >= 1

    # 4. Test GET /manufacturers
    res_all_mfg = client.get("/api/v1/manufacturers")
    assert res_all_mfg.status_code == 200
    mfgs = res_all_mfg.json()
    assert any(m["knx_id"] == "M-00C5" for m in mfgs)

    # 5. Test stats
    res_stats = client.get("/api/v1/stats")
    assert res_stats.status_code == 200
    stats = res_stats.json()
    assert stats["devices_total"] >= 1
    assert stats["manufacturers_total"] >= 1

    # 6. Test Web Frontend HTML
    res_html = client.get("/")
    assert res_html.status_code == 200
    assert "KoNfiX-Database" in res_html.text
