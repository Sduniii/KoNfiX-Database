import pytest
from app.services.knxprod_parser import parse_knxprod_bytes
from scripts.create_sample_knxprod import create_sample_knxprod_archive

def test_parse_valid_knxprod(sample_knxprod_bytes):
    parsed = parse_knxprod_bytes(sample_knxprod_bytes)

    assert parsed.manufacturer_id == "M-0083"
    assert parsed.manufacturer_name == "MDT technologies"
    assert len(parsed.devices) == 1

    dev = parsed.devices[0]
    assert dev.order_number == "AKS-0816.04"
    assert "Schaltaktor" in dev.name
    assert dev.bus_current_ma == 12.0
    assert len(dev.applications) == 1

    app = dev.applications[0]
    assert app.name == "Schalten 8f 16A"
    assert app.version == "4.2"
    assert app.mask_version == "MV-07B0"
    assert app.com_objects_count == 4
    assert app.parameters_count == 2

def test_parse_corrupt_zip():
    with pytest.raises(ValueError, match="Keine gültige ZIP-Datei"):
        parse_knxprod_bytes(b"corrupted binary data not a zip")

def test_parse_zip_without_xml():
    import io, zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", "no xml here")
    
    with pytest.raises(ValueError, match="Keine XML-Metadatendatei"):
        parse_knxprod_bytes(buf.getvalue())


def test_parse_anonymous_mdt_hardware_xml():
    """Simulates real ETS export where Hardware.xml has <Manufacturer RefId='M-0083'> without Name attribute."""
    import io, zipfile
    xml_no_name = """<?xml version="1.0" encoding="utf-8"?>
<KNX xmlns="http://knx.org/xml/project/20">
  <ManufacturerData>
    <Manufacturer RefId="M-0083">
      <Hardware Id="M-0083_H-AKU" Name="Universalaktor 2-fach UP" VersionNumber="1">
        <Products>
          <Product Id="M-0083_P-AKU" OrderNumber="AKU-02UP.03" Text="AKU-02UP.03 Universal Actuator 2-fold" />
        </Products>
      </Hardware>
    </Manufacturer>
  </ManufacturerData>
</KNX>"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("M-0083/Hardware.xml", xml_no_name.encode("utf-8"))

    parsed = parse_knxprod_bytes(buf.getvalue())
    assert parsed.manufacturer_id == "M-0083"
    assert parsed.manufacturer_name == "MDT technologies"
    assert len(parsed.devices) == 1
    assert parsed.devices[0].order_number == "AKU-02UP.03"


def test_parse_openknx():
    """Tests that M-00FA with OpenKNX context is recognized as OpenKNX."""
    import io, zipfile
    xml_openknx = """<?xml version="1.0" encoding="utf-8"?>
<KNX xmlns="http://knx.org/xml/project/20">
  <ManufacturerData>
    <Manufacturer RefId="M-00FA">
      <Hardware Id="M-00FA_H-1" Name="OpenKNX Modul">
        <Products>
          <Product Id="M-00FA_P-1" OrderNumber="OKNX-01" Text="OpenKNX Logic Modul" />
        </Products>
      </Hardware>
    </Manufacturer>
  </ManufacturerData>
</KNX>"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("M-00FA/Hardware.xml", xml_openknx.encode("utf-8"))

    parsed = parse_knxprod_bytes(buf.getvalue())
    assert parsed.manufacturer_id == "M-00FA"
    assert parsed.manufacturer_name == "OpenKNX"
    assert parsed.devices[0].order_number == "OKNX-01"
