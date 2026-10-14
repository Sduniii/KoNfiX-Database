import json
import pytest
from fastapi.testclient import TestClient
from app.main import app

SAMPLE_YAML_WITH_TRANSLATIONS = """
$schema: https://db.konfix.sduni.de/schemas/konfix-device-v1.json
konfix_version: '1.0'
manufacturer:
  code: openknx
  name: OpenKNX Community
device:
  order_number: TEST-TRANS-01
  name: Test Aktor mit Übersetzungen
  description: Testgerät für Übersetzungen
  hardware:
    name: TEST-TRANS-HW
    version: '1.0'
    bus_current_ma: 10.0
application:
  id: openknx_test-trans_v1
  name: Test App
  version: '1.0'
  mask_version: MV-07B0
communication_objects:
  - id: openknx_o-1
    number: 1
    name: Kanal A Schalten
    function: Ein/Aus
    dpt: 1.001
    size: 1 Bit
    flags:
      communication: true
      read: false
      write: true
      transmit: false
      update: false
parameters:
  - id: openknx_p-1
    name: Betriebsart Kanal A
    text: Betriebsart Kanal A
    type: enum
    default: '1'
    page: Allgemein
translations:
  openknx_p-1:
    de: Betriebsart Kanal A
    en: Operating mode Channel A
  openknx_o-1:
    de: Kanal A Schalten
    en: Channel A Switching
"""


def test_editor_html_contains_translation_elements(client):
    """Verify index.html contains the new Translations tab, datalist, and controls."""
    res = client.get("/")
    assert res.status_code == 200
    html = res.text

    assert 'id="tabEditorTransBtn"' in html
    assert 'id="editorTransCount"' in html
    assert 'id="editorTabTrans"' in html
    assert 'id="editorTransSearch"' in html
    assert 'id="editorTransFilter"' in html
    assert 'id="editorAddTransBtn"' in html
    assert 'id="editorAutoPopulateTransBtn"' in html
    assert 'id="editorTransEntityDatalist"' in html
    assert 'id="editorTransPagination"' in html
    assert 'id="editorTransList"' in html
    assert 'id="editorTransPaginationBottom"' in html


def test_device_translations_api_and_counts(client):
    """Upload a device YAML with translations and verify GET /devices/{order_number}/translations."""
    upload_res = client.post(
        "/api/v1/upload",
        content=SAMPLE_YAML_WITH_TRANSLATIONS.encode("utf-8"),
        headers={"Content-Type": "application/x-yaml", "X-File-Name": "test-trans.yaml"}
    )
    assert upload_res.status_code in (200, 201), upload_res.text

    # 1. Check Device detail includes translations_count
    dev_res = client.get("/api/v1/devices/TEST-TRANS-01")
    assert dev_res.status_code == 200
    dev_data = dev_res.json()
    assert dev_data["translations_count"] == 4  # 2 entities x 2 languages = 4 translations rows

    # 2. Check GET /devices/{order_number}/translations endpoint
    trans_res = client.get("/api/v1/devices/TEST-TRANS-01/translations")
    assert trans_res.status_code == 200
    trans_list = trans_res.json()
    assert len(trans_list) == 4

    # 3. Filter by language=en
    en_res = client.get("/api/v1/devices/TEST-TRANS-01/translations?language=en")
    assert en_res.status_code == 200
    en_items = en_res.json()
    assert len(en_items) == 2
    assert all(t["language"] == "en" for t in en_items)

    # 4. Filter by entity_id=openknx_p-1
    param_res = client.get("/api/v1/devices/TEST-TRANS-01/translations?entity_id=openknx_p-1")
    assert param_res.status_code == 200
    param_items = param_res.json()
    assert len(param_items) == 2
    assert all(t["entity_id"] == "openknx_p-1" for t in param_items)

    # 5. Search with q
    q_res = client.get("/api/v1/devices/TEST-TRANS-01/translations?q=Switching")
    assert q_res.status_code == 200
    q_items = q_res.json()
    assert len(q_items) == 1
    assert q_items[0]["entity_id"] == "openknx_o-1"
    assert q_items[0]["text"] == "Channel A Switching"

    # 6. Verify 404 for unknown device
    res_404 = client.get("/api/v1/devices/UNKNOWN-DEVICE-999/translations")
    assert res_404.status_code == 404
