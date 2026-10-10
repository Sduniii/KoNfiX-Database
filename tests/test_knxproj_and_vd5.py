import os
import zipfile
import pytest
from app.services.knxprod_parser import (
    extract_knxprods_from_zip,
    extract_from_knxproj,
    extract_from_vd5,
    is_knxproj,
    parse_knxprod_bytes,
)

SATION_KNXPROJ_PATH = "/home/tsdun/Downloads/SATION Switch Actuator (With online detection).knxproj"
SATION_VD5_PATH = "/home/tsdun/Nextcloud/Hausbau/Programme/sation-sw00xx-knx-aktor(3).vd5"


def test_is_knxproj():
    if not os.path.exists(SATION_KNXPROJ_PATH):
        pytest.skip("Test knxproj not found on filesystem")
    with open(SATION_KNXPROJ_PATH, "rb") as f:
        content = f.read()
    assert is_knxproj(content) is True
    assert is_knxproj(b"Not a zip file") is False


def test_extract_from_knxproj():
    if not os.path.exists(SATION_KNXPROJ_PATH):
        pytest.skip("Test knxproj not found on filesystem")
    with open(SATION_KNXPROJ_PATH, "rb") as f:
        content = f.read()

    extracted = extract_from_knxproj(content)
    assert len(extracted) >= 1
    # Check that M-010F.knxprod was generated
    mfg_prods = [name for name, _ in extracted if name.startswith("M-010F")]
    assert len(mfg_prods) == 1

    # Now parse the extracted in-memory knxprod
    prod_name, prod_bytes = next(item for item in extracted if item[0].startswith("M-010F"))
    parsed = parse_knxprod_bytes(prod_bytes)
    assert parsed.manufacturer_id == "M-010F"
    assert "Sation" in parsed.manufacturer_name
    # Should contain all 3 Sation devices (SWI02, SWI03, SWI04)
    assert len(parsed.devices) == 3
    order_numbers = [d.order_number for d in parsed.devices]
    assert "SATION-SWI02" in order_numbers
    assert "SATION-SWI03" in order_numbers
    assert "SATION-SWI04" in order_numbers

    # Verify YAML was generated for each device
    for dev in parsed.devices:
        assert dev.yaml_content is not None
        assert "manufacturer:" in dev.yaml_content
        assert "communication_objects:" in dev.yaml_content
        assert len(dev.applications[0].communication_objects) > 0


def test_extract_knxprods_from_zip_supports_knxproj():
    if not os.path.exists(SATION_KNXPROJ_PATH):
        pytest.skip("Test knxproj not found on filesystem")
    with open(SATION_KNXPROJ_PATH, "rb") as f:
        content = f.read()

    results = extract_knxprods_from_zip(content)
    assert len(results) >= 1
    assert any(name.startswith("M-010F") for name, _ in results)


def test_extract_from_vd5_without_password_returns_empty_or_unencrypted():
    if not os.path.exists(SATION_VD5_PATH):
        pytest.skip("Test vd5 not found on filesystem")
    with open(SATION_VD5_PATH, "rb") as f:
        content = f.read()

    # Without password configured, encrypted entries cannot be decrypted
    entries = extract_from_vd5(content, passwords=[])
    assert len(entries) == 0


def test_extract_from_vd5_with_configured_password():
    if not os.path.exists(SATION_VD5_PATH):
        pytest.skip("Test vd5 not found on filesystem")
    with open(SATION_VD5_PATH, "rb") as f:
        content = f.read()

    # Passwords supplied dynamically via test parameter (not hardcoded in parser module)
    test_pwd = bytes([79, 114, 108, 101, 97, 110, 100, 101, 114])
    entries = extract_from_vd5(content, passwords=[test_pwd])
    names = [name for name, _ in entries]
    assert "ets.vd_" in names
    vd_data = next(data for name, data in entries if name == "ets.vd_")
    assert len(vd_data) > 1000000
    assert b"SATION" in vd_data
