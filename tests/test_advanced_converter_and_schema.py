import json
import io
import zipfile
import pytest
import yaml

from app.services.yaml_converter import (
    sanitize_id,
    generate_manufacturer_code,
    build_konfix_yaml,
    parse_konfix_yaml,
)
from app.services.knxprod_parser import parse_knxprod_bytes


def test_sanitize_id_lowercase_schema():
    # Exactly like user requested: mdt_a-1234_p-1 (everything lowercase)
    assert sanitize_id("M-0083_A-1234_P-1", "mdt") == "mdt_a-1234_p-1"
    assert sanitize_id("M-0083_A-0083-10-7B1A_P-1", "mdt") == "mdt_a-0083-10-7b1a_p-1"
    assert sanitize_id("M-00FA_O-4", "openknx") == "openknx_o-4"
    assert sanitize_id("P-1", "mdt") == "mdt_p-1"
    assert sanitize_id("mdt_P-1", "mdt") == "mdt_p-1"
    assert sanitize_id("UP-2", "abb") == "abb_up-2"


def test_schema_api_endpoints(client):
    # Test GET /api/v1/schema/konfix-device-v1.json
    res1 = client.get("/api/v1/schema/konfix-device-v1.json")
    assert res1.status_code == 200
    assert "application/schema+json" in res1.headers["content-type"]
    schema1 = res1.json()
    assert schema1["$id"] == "https://konfix.sduni.de/schemas/konfix-device-v1.json"
    assert "properties" in schema1
    assert "manufacturer" in schema1["properties"]

    # Test GET /schemas/konfix-device-v1.json
    res2 = client.get("/schemas/konfix-device-v1.json")
    assert res2.status_code == 200
    schema2 = res2.json()
    assert schema2["title"] == "KoNfiX Device Definition Schema v1"


def test_translation_and_dynamic_extraction():
    """Verify that translations, dynamic tree (choose/when/depends_on), and assign rules are extracted."""
    xml_content = """<?xml version="1.0" encoding="utf-8"?>
<KNX xmlns="http://knx.org/xml/project/20">
  <ManufacturerData>
    <Manufacturer RefId="M-0083" Name="MDT technologies">
      <Languages>
        <Language Identifier="de-DE">
          <TranslationUnit RefId="TU-1">
            <TranslationElement RefId="M-0083_P-1">
              <Translation AttributeName="Text" Text="Betriebsart Kanal A" />
            </TranslationElement>
            <TranslationElement RefId="M-0083_P-2">
              <Translation AttributeName="Text" Text="Fahrzeit Lamelle" />
            </TranslationElement>
            <TranslationElement RefId="M-0083_O-1">
              <Translation AttributeName="Text" Text="Kanal A Auf/Ab" />
              <Translation AttributeName="FunctionText" Text="Fahrbefehl" />
            </TranslationElement>
          </TranslationUnit>
        </Language>
        <Language Identifier="en-US">
          <TranslationUnit RefId="TU-2">
            <TranslationElement RefId="M-0083_P-1">
              <Translation AttributeName="Text" Text="Operating mode Channel A" />
            </TranslationElement>
            <TranslationElement RefId="M-0083_P-2">
              <Translation AttributeName="Text" Text="Slat move time" />
            </TranslationElement>
          </TranslationUnit>
        </Language>
      </Languages>

      <ApplicationPrograms>
        <ApplicationProgram Id="M-0083_A-1234" Name="Jalousieaktor 4-fach" ApplicationVersion="1.0" MaskVersion="MV-07B0">
          <Static>
            <ComObjectTable>
              <ComObject Id="M-0083_O-1" Name="Channel A Move" Number="1" FunctionText="Move" ObjectSize="1 Bit" DatapointType="1.008" />
            </ComObjectTable>
          </Static>
          <Parameters>
            <Parameter Id="M-0083_P-1" Name="Mode" Value="1" ParameterTypeRefId="M-0083_PT-1" />
            <Parameter Id="M-0083_P-2" Name="MoveTime" Value="50" ParameterTypeRefId="M-0083_PT-2" />
          </Parameters>
          <ParameterTypes>
            <ParameterType Id="M-0083_PT-1" Name="ModeType">
              <TypeRestriction Base="Value">
                <Enumeration Value="1" Text="Jalousie" />
                <Enumeration Value="2" Text="Rollladen" />
              </TypeRestriction>
            </ParameterType>
            <ParameterType Id="M-0083_PT-2" Name="TimeType" />
          </ParameterTypes>
          <Dynamic>
            <Channel Id="CH-1" Name="Kanal A">
              <ParameterBlock Id="PB-1" Name="Zeiteinstellungen">
                <ParameterSeparator Id="PS-1" Text="Verzögerungen" />
                <ParameterRefRef RefId="M-0083_P-1" />
                <choose ParamRefId="M-0083_P-1">
                  <when test="1">
                    <ParameterRefRef RefId="M-0083_P-2" />
                    <ComObjectRefRef RefId="M-0083_O-1" />
                    <Assign TargetParamRefRef="M-0083_P-2" Value="100" />
                  </when>
                </choose>
              </ParameterBlock>
            </Channel>
          </Dynamic>
        </ApplicationProgram>
      </ApplicationPrograms>

      <Hardware Id="M-0083_H-1" Name="JAL-0410.02" VersionNumber="1">
        <Products>
          <Product Id="M-0083_PROD-1" OrderNumber="JAL-0410.02" Text="Jalousieaktor 4-fach 10A" />
        </Products>
        <Hardware2Programs>
          <Hardware2Program Id="H2P-1" ApplicationProgramRefId="M-0083_A-1234" />
        </Hardware2Programs>
      </Hardware>
    </Manufacturer>
  </ManufacturerData>
</KNX>"""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("M-0083.xml", xml_content.encode("utf-8"))

    parsed = parse_knxprod_bytes(buf.getvalue())
    assert parsed.manufacturer_code == "mdt"
    assert len(parsed.devices) == 1

    dev = parsed.devices[0]
    assert dev.order_number == "JAL-0410.02"
    assert dev.yaml_content is not None

    yaml_data = yaml.safe_load(dev.yaml_content)
    assert yaml_data["$schema"] == "https://konfix.sduni.de/schemas/konfix-device-v1.json"
    assert yaml_data["manufacturer"]["code"] == "mdt"

    # Verify Parameters
    params = yaml_data["parameters"]
    assert len(params) == 2
    
    # Check ID schema: lowercase mdt_p-1
    p1 = next(p for p in params if p["id"] == "mdt_p-1")
    assert p1["name"] == "Betriebsart Kanal A"  # German resolved text
    assert p1["translations"]["de"] == "Betriebsart Kanal A"
    assert p1["translations"]["en"] == "Operating mode Channel A"

    p2 = next(p for p in params if p["id"] == "mdt_p-2")
    assert p2["name"] == "Fahrzeit Lamelle"
    assert p2["page"] == "Kanal A > Zeiteinstellungen"
    assert p2["section"] == "Verzögerungen"
    assert "depends_on" in p2
    assert p2["depends_on"]["param_id"] == "mdt_p-1"
    assert p2["depends_on"]["when_values"] == ["1"]

    # Verify Communication Objects
    cos = yaml_data["communication_objects"]
    assert len(cos) == 1
    co1 = cos[0]
    assert co1["id"] == "mdt_o-1"
    assert co1["name"] == "Kanal A Auf/Ab"
    assert co1["function"] == "Fahrbefehl"
    assert "depends_on" in co1
    assert co1["depends_on"]["param_id"] == "mdt_p-1"

    # Verify Assign Rules
    assert "assign_rules" in yaml_data
    assigns = yaml_data["assign_rules"]
    assert len(assigns) == 1
    assert assigns[0]["target"] == "mdt_p-2"
    assert assigns[0]["value"] == "100"
    assert assigns[0]["conditions"][0]["param_id"] == "mdt_p-1"
    assert assigns[0]["conditions"][0]["when_values"] == ["1"]
