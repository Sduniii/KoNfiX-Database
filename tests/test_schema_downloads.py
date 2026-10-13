import pytest

def test_json_schema_endpoint(client):
    """Test GET /api/v1/schema/konfix-device-v1.json returns valid schema JSON."""
    res = client.get("/api/v1/schema/konfix-device-v1.json")
    assert res.status_code == 200
    assert "json" in res.headers["content-type"]
    data = res.json()
    assert "$schema" in data or "title" in data or "properties" in data

def test_json_schema_download_attachment(client):
    """Test GET /api/v1/schema/konfix-device-v1.json?download=true returns attachment."""
    res = client.get("/api/v1/schema/konfix-device-v1.json?download=true")
    assert res.status_code == 200
    assert "attachment" in res.headers.get("content-disposition", "")
    assert "konfix-device-v1.json" in res.headers.get("content-disposition", "")

def test_yaml_template_download(client):
    """Test GET /api/v1/schema/template.yaml returns downloadable YAML starter template."""
    res = client.get("/api/v1/schema/template.yaml")
    assert res.status_code == 200
    assert "yaml" in res.headers.get("content-type", "") or "text/plain" in res.headers.get("content-type", "")
    assert "attachment" in res.headers.get("content-disposition", "")
    content = res.text
    assert "konfix_version:" in content
    assert "communication_objects:" in content
    assert "parameters:" in content

def test_root_shortcut_routes(client):
    """Test GET /schema.json and GET /template.yaml shortcuts."""
    res_schema = client.get("/schema.json")
    assert res_schema.status_code == 200

    res_template = client.get("/template.yaml")
    assert res_template.status_code == 200
    assert "konfix_version:" in res_template.text
