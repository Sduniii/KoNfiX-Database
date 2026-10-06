import pytest
from app.services.knxprod_parser import parse_knxprod_bytes
from scripts.create_sample_knxprod import create_sample_knxprod_archive

def test_parse_valid_knxprod(sample_knxprod_bytes):
    parsed = parse_knxprod_bytes(sample_knxprod_bytes)

    assert parsed.manufacturer_id == "M-00C5"
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
