import io
import zipfile
from pathlib import Path

def create_sample_knxprod_archive(
    mfg_id: str,
    mfg_name: str,
    order_number: str,
    product_name: str,
    hardware_name: str,
    app_name: str,
    app_version: str,
    mask_version: str = "MV-07B0",
    bus_current_ma: float = 12.0
) -> bytes:
    """
    Constructs an in-memory valid .knxprod ZIP container with standard KNX XML structure.
    """
    xml_content = f"""<?xml version="1.0" encoding="utf-8"?>
<KNX xmlns="http://knx.org/xml/project/20">
  <ManufacturerData>
    <Manufacturer RefId="{mfg_id}" Name="{mfg_name}">
      <ApplicationPrograms>
        <ApplicationProgram Id="{mfg_id}_A_{order_number}"
                            Name="{app_name}"
                            ApplicationVersion="{app_version}"
                            ProgramVersion="{app_version}"
                            MaskVersion="{mask_version}">
          <Static>
            <ComObjectTable>
              <ComObject Id="O-1" Name="Kanal A Schalten" Number="1" FunctionText="Schalten Ein/Aus" />
              <ComObject Id="O-2" Name="Kanal A Status" Number="2" FunctionText="Status Rückmeldung" />
              <ComObject Id="O-3" Name="Kanal B Schalten" Number="3" FunctionText="Schalten Ein/Aus" />
              <ComObject Id="O-4" Name="Kanal B Status" Number="4" FunctionText="Status Rückmeldung" />
            </ComObjectTable>
          </Static>
          <Parameters>
            <Parameter Id="P-1" Name="Relaisfunktion" Value="Schließer" />
            <Parameter Id="P-2" Name="Verhalten bei Busspannungsausfall" Value="Keine Änderung" />
          </Parameters>
        </ApplicationProgram>
      </ApplicationPrograms>

      <Hardware Id="{mfg_id}_H_{order_number}"
                Name="{hardware_name}"
                VersionNumber="1"
                BusCurrent="{bus_current_ma}">
        <Products>
          <Product Id="{mfg_id}_P_{order_number}"
                   OrderNumber="{order_number}"
                   Text="{product_name}"
                   Description="{product_name} für KNX-Bussysteme" />
        </Products>
        <Hardware2Programs>
          <Hardware2Program Id="{mfg_id}_H2P_{order_number}"
                            ApplicationProgramRefId="{mfg_id}_A_{order_number}" />
        </Hardware2Programs>
      </Hardware>

      <Catalog>
        <CatalogSection Id="CS-1" Name="Aktoren">
          <CatalogItem Id="CI-1"
                       Name="{product_name}"
                       Number="{order_number}"
                       ProductRefId="{mfg_id}_P_{order_number}"
                       Hardware2ProgramRefId="{mfg_id}_H2P_{order_number}" />
        </CatalogSection>
      </Catalog>
    </Manufacturer>
  </ManufacturerData>
</KNX>"""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{mfg_id}.xml", xml_content.encode("utf-8"))
        zf.writestr("signature.txt", f"Sample signature for {mfg_id}".encode("utf-8"))

    return buf.getvalue()

if __name__ == "__main__":
    out_dir = Path("catalog_files")
    out_dir.mkdir(exist_ok=True)
    
    samples = [
        ("M-00C5", "MDT technologies", "AKS-0816.04", "Schaltaktor 8-fach 16A", "Schaltaktor Standard", "Schalten 8f 16A", "4.2", "MV-07B0", 12.0),
        ("M-0002", "ABB Stotz-Kontakt GmbH", "SA/S8.16.6.2", "Schaltaktor 8-fach 16A C-Last", "SA/S Aktor", "Schalten 8f 16A C-Last", "2.1", "MV-07B0", 10.0),
        ("M-0083", "Gira Giersiepen GmbH", "216800", "Dimmaktor 4-fach Komfort", "Dimmaktor REG", "Dimmen 4f Komfort", "1.3", "MV-07B0", 15.0),
        ("M-0077", "Theben AG", "RMG 8 S KNX", "Schaltaktor Grundmodul 8-fach", "RMG 8 S", "Schalten RMG 8", "3.0", "MV-07B0", 8.5)
    ]

    for mfg_id, mfg_name, order_no, prod_name, hw_name, app_name, app_ver, mask, bus in samples:
        filename = f"{mfg_id}_{order_no.replace('/', '_')}.knxprod"
        data = create_sample_knxprod_archive(mfg_id, mfg_name, order_no, prod_name, hw_name, app_name, app_ver, mask, bus)
        (out_dir / filename).write_bytes(data)
        print(f"Generated sample: {filename} ({len(data)} bytes)")
