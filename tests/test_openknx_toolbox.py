import asyncio
import io
import struct
import zipfile
import pytest

from app.models import Manufacturer, Device, ApplicationProgram, KnxGateway
from app.services.openknx import (
    task_runner,
    release_service,
    knxprod_generator,
    calculate_crc16,
    KnxConnection,
    KnxGatewayDiscovery,
    SEARCH_REQUEST,
    SEARCH_RESPONSE,
    FileTransferClient,
    parse_knx_address,
    format_knx_address,
)
from app.services.openknx.release_service import parse_semver_tuple, compare_semver


def test_semver_parsing_and_comparison():
    assert parse_semver_tuple("v1.10.0-Dev") == (1, 10, 0, "Dev")
    assert parse_semver_tuple("3.5.2") == (3, 5, 2, "")
    assert parse_semver_tuple("v0.1.0-alpha.1") == (0, 1, 0, "alpha.1")

    # 1.10.0 > 1.9.0
    assert compare_semver("1.10.0", "1.9.0") == 1
    assert compare_semver("1.9.0", "1.10.0") == -1
    # 1.0.0 (stable) > 1.0.0-Dev (prerelease)
    assert compare_semver("1.0.0", "1.0.0-Dev") == 1
    assert compare_semver("1.0.0-Dev", "1.0.0") == -1
    # Equal
    assert compare_semver("2.1.0", "v2.1.0") == 0


def test_crc16_modbus():
    # Test vector for CRC16/MODBUS: "123456789" -> 0x4B37
    test_bytes = b"123456789"
    crc = calculate_crc16(test_bytes)
    assert crc == 0x4B37


def test_knx_address_parsing():
    assert parse_knx_address("1.1.30") == ((1 << 12) | (1 << 8) | 30)
    assert format_knx_address(0x111E) == "1.1.30"
    assert parse_knx_address("15.15.255") == 0xFFFF
    assert format_knx_address(0xFFFF) == "15.15.255"

    with pytest.raises(ValueError):
        parse_knx_address("1.1")


def test_knxnet_ip_framing():
    conn = KnxConnection("127.0.0.1", 3671)
    target = parse_knx_address("1.1.30")
    apdu = bytes([0x80])  # U_Connect
    cemi = conn._build_cemi_l_data_req(target, apdu)

    # Validate cEMI header: 0x11 (L_Data.req), 0, 0xBC (ctrl1), 0x60 (ctrl2)
    assert cemi[0] == 0x11
    assert cemi[1] == 0x00
    assert cemi[2] == 0xBC
    assert cemi[3] == 0x60
    # Destination address (1.1.30 = 0x111E)
    dest = struct.unpack("!H", cemi[6:8])[0]
    assert dest == target


def test_knxprod_generation():
    async def _run():
        sample_xml = b"""<?xml version="1.0" encoding="utf-8"?>
<KNX xmlns="http://knx.org/xml/project/20">
  <ManufacturerData>
    <Manufacturer RefId="M-00FA">
      <Catalog>
        <CatalogSection Id="M-00FA_CS-1" Name="OpenKNX">
          <CatalogItem Id="M-00FA_CI-1" Name="Test Device" ProductRefId="M-00FA_P-1" Hardware2ProgramRefId="M-00FA_HP-1" />
        </CatalogSection>
      </Catalog>
    </Manufacturer>
  </ManufacturerData>
</KNX>"""
        baggages = {"A1/icon.png": b"\x89PNG\r\n\x1a\nfake"}
        knxprod_bytes = await knxprod_generator.generate_knxprod_bytes(
            sample_xml, baggages=baggages, manufacturer_id="M-00FA"
        )

        assert len(knxprod_bytes) > 0
        with zipfile.ZipFile(io.BytesIO(knxprod_bytes)) as zf:
            names = zf.namelist()
            assert "M-00FA.xml" in names
            assert "M-00FA/Baggages/A1/icon.png" in names
            assert "knx_master.xml" in names

    asyncio.run(_run())


def test_task_runner_lifecycle():
    async def _run():
        async def sample_task(task_obj):
            task_obj.progress = 50
            task_obj.message = "Halbzeit"
            task_obj.logs.append("Step 1 done")

        task = task_runner.create_task("Unit Test Task", "test", sample_task)
        assert task.task_id is not None
        assert task.name == "Unit Test Task"

        # Wait for completion
        for _ in range(20):
            if task.status == "completed":
                break
            await asyncio.sleep(0.05)

        assert task.status == "completed"
        assert task.progress == 100

        # Cancel test
        async def long_task(task_obj):
            for _ in range(100):
                await asyncio.sleep(0.1)

        t2 = task_runner.create_task("Cancel Me", "test", long_task)
        cancelled = task_runner.cancel_task(t2.task_id)
        assert cancelled is True
        assert t2.status == "cancelled"

    asyncio.run(_run())


def test_openknx_api_endpoints(client):
    # 1. Gateways CRUD
    gw_payload = {
        "name": "Test IP Router",
        "host": "192.168.1.100",
        "port": 3671,
        "protocol": "tunneling_udp",
        "individual_address": "1.1.250",
        "is_default": True
    }
    r = client.post("/api/v1/openknx/gateways", json=gw_payload)
    assert r.status_code == 200
    gw_data = r.json()
    assert gw_data["name"] == "Test IP Router"
    assert gw_data["is_default"] is True
    gw_id = gw_data["id"]

    # List gateways
    r = client.get("/api/v1/openknx/gateways")
    assert r.status_code == 200
    gws = r.json()
    assert any(g["id"] == gw_id for g in gws)

    # 2. Devices (cached mDNS)
    r = client.get("/api/v1/openknx/devices")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    # 3. Tasks listing
    r = client.get("/api/v1/openknx/tasks")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    # 4. Delete gateway
    r = client.delete(f"/api/v1/openknx/gateways/{gw_id}")
    assert r.status_code == 200


def test_1click_import_openknx_xml(db):
    """Verifies that an OpenKNX XML can be ingested and becomes a searchable device in the catalog."""
    xml_data = b"""<?xml version="1.0" encoding="utf-8"?>
<KNX xmlns="http://knx.org/xml/project/20">
  <ManufacturerData>
    <Manufacturer RefId="M-00FA">
      <Catalog>
        <CatalogSection Id="M-00FA_CS-1" Name="OpenKNX">
          <CatalogItem Id="M-00FA_CI-OAM-TEST" Name="OpenKNX Testmodul" Number="1" ProductRefId="M-00FA_P-TEST" Hardware2ProgramRefId="M-00FA_HP-TEST" />
        </CatalogSection>
      </Catalog>
      <ApplicationPrograms>
        <ApplicationProgram Id="M-00FA_A-TEST" Name="App Testmodul" ApplicationNumber="100" ApplicationVersion="1" MaskVersion="MV-07B0">
          <Static>
            <ComObjectTable>
              <ComObject Id="M-00FA_A-TEST_O-1" Name="Kanal 1" Number="1" Text="Schalten" FunctionText="Ein/Aus" ObjectSize="1 Bit" ReadFlag="Enabled" WriteFlag="Enabled" CommunicationFlag="Enabled" TransmitFlag="Enabled" UpdateFlag="Disabled" />
            </ComObjectTable>
          </Static>
        </ApplicationProgram>
      </ApplicationPrograms>
      <Hardware>
        <Hardware Id="M-00FA_H-TEST" Name="OpenKNX Test Hardware" SerialNumber="TEST-001" Version="1">
          <Products>
            <Product Id="M-00FA_P-TEST" Text="OpenKNX Testmodul" OrderNumber="OKNX-TEST-01" IsRailMounted="true" DefaultLanguage="de-DE" />
          </Products>
          <Hardware2Programs>
            <Hardware2Program Id="M-00FA_HP-TEST" MediumTypes="MT-0">
              <ApplicationProgramRef RefId="M-00FA_A-TEST" />
            </Hardware2Program>
          </Hardware2Programs>
        </Hardware>
      </Hardware>
    </Manufacturer>
  </ManufacturerData>
</KNX>"""

    # Wrap into synthetic release ZIP
    synthetic_zip = io.BytesIO()
    with zipfile.ZipFile(synthetic_zip, "w") as zf:
        zf.writestr("data/TestModul.xml", xml_data)

    mock_releases = {
        "OAM-Test": {
            "releases": [
                {
                    "tag_name": "v1.0.0",
                    "html_url": "https://github.com/OpenKNX/OAM-Test/releases/tag/v1.0.0",
                    "assets": [
                        {
                            "name": "TestModul-Release-1.0.0.zip",
                            "browser_download_url": "https://example.com/mock.zip"
                        }
                    ]
                }
            ]
        }
    }

    original_get_releases = release_service.get_releases
    original_download_asset = release_service.download_asset

    async def _mock_get_releases(force_refresh=False):
        return mock_releases

    async def _mock_download_asset(url, target_path, progress_cb=None):
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(synthetic_zip.getvalue())
        return target_path

    release_service.get_releases = _mock_get_releases
    release_service.download_asset = _mock_download_asset

    async def _run():
        res = await release_service.import_release_to_catalog("OAM-Test", "v1.0.0", db)
        assert res["status"] == "success"
        assert len(res["devices_imported"]) == 1
        assert res["devices_imported"][0]["order_number"] == "OKNX-TEST-01"

        # Verify device is in database
        dev = db.query(Device).filter(Device.order_number == "OKNX-TEST-01").first()
        assert dev is not None
        assert dev.name == "OpenKNX Testmodul"
        assert dev.manufacturer.name == "OpenKNX"
        assert dev.manufacturer.knx_id == "M-00FA"

        # Verify application program was stored relationally
        apps = db.query(ApplicationProgram).filter(ApplicationProgram.device_id == dev.id).all()
        assert len(apps) == 1
        assert apps[0].name == "App Testmodul"
        assert apps[0].com_objects_count == 1

    try:
        asyncio.run(_run())
    finally:
        release_service.get_releases = original_get_releases
        release_service.download_asset = original_download_asset


def test_openknx_ui_integration(client):
    """
    Verifies that the HTML interface includes the OpenKNX Toolbox Extra,
    the navbar button, all 7 tab panels, the JavaScript assets, and CSS styles.
    """
    # 1. Main Page contains OpenKNX Toolbox UI elements
    res = client.get("/")
    assert res.status_code == 200
    html = res.text
    assert "openOpenKnxToolboxBtn" in html
    assert "openknxToolboxModal" in html
    assert "openknxTabReleases" in html
    assert "openknxTabDevices" in html
    assert "openknxTabFiles" in html
    assert "openknxTabFlash" in html
    assert "openknxTabGateways" in html
    assert "openknxTabKnxprod" in html
    assert "openknxTabTasks" in html
    assert "/static/openknx_toolbox.js" in html

    # 2. OpenKNX JS asset is served and valid
    js_res = client.get("/static/openknx_toolbox.js")
    assert js_res.status_code == 200
    assert "initOpenKnxToolbox" in js_res.text
    assert "openknxState" in js_res.text

    # 3. i18n contains openknx translations
    i18n_res = client.get("/static/i18n.js")
    assert i18n_res.status_code == 200
    assert "openknx:" in i18n_res.text
    assert "openknxToolbox:" in i18n_res.text

    # 4. CSS contains openknx modal styles
    css_res = client.get("/static/style.css")
    assert css_res.status_code == 200
    assert ".modal-openknx" in css_res.text
    assert ".openknx-nav-tabs" in css_res.text

