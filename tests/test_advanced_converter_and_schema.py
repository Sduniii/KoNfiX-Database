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
    # Inline translations must not be on the parameter itself
    assert "translations" not in p1

    p2 = next(p for p in params if p["id"] == "mdt_p-2")
    assert p2["name"] == "Fahrzeit Lamelle"
    assert p2["page"] == "Kanal A > Zeiteinstellungen"
    assert p2["section"] == "Verzögerungen"
    assert "depends_on" in p2
    assert p2["depends_on"]["param_id"] == "mdt_p-1"
    assert p2["depends_on"]["when_values"] == ["1"]
    assert "conditions" not in p2["depends_on"]

    # Verify dedicated root-level translations block
    assert "translations" in yaml_data
    tr_block = yaml_data["translations"]
    assert tr_block["mdt_p-1"]["de"] == "Betriebsart Kanal A"
    assert tr_block["mdt_p-1"]["en"] == "Operating mode Channel A"
    assert tr_block["mdt_o-1"]["de"] == "Kanal A Auf/Ab"

    # Verify Communication Objects
    cos = yaml_data["communication_objects"]
    assert len(cos) == 1
    co1 = cos[0]
    assert co1["id"] == "mdt_o-1"
    assert co1["name"] == "Kanal A Auf/Ab"
    assert co1["function"] == "Fahrbefehl"
    assert "translations" not in co1
    assert "depends_on" in co1
    assert co1["depends_on"]["param_id"] == "mdt_p-1"
    assert co1["depends_on"]["when_values"] == ["1"]
    assert "conditions" not in co1["depends_on"]

    # Verify Assign Rules
    assert "assign_rules" in yaml_data
    assigns = yaml_data["assign_rules"]
    assert len(assigns) == 1
    assert assigns[0]["target"] == "mdt_p-2"
    assert assigns[0]["value"] == "100"
    assert assigns[0]["conditions"][0]["param_id"] == "mdt_p-1"
    assert assigns[0]["conditions"][0]["when_values"] == ["1"]


def test_modular_dynamic_tree_and_pref_resolution():
    """Verify recursive module dynamic trees and pref_map resolution (e.g. for MDT AKU)."""
    xml_content = """<?xml version="1.0" encoding="utf-8"?>
<KNX xmlns="http://knx.org/xml/project/20">
  <ManufacturerData>
    <Manufacturer RefId="M-0083" Name="MDT technologies">
      <ApplicationPrograms>
        <ApplicationProgram Id="M-0083_A-9999" Name="Modularer Aktor" ApplicationVersion="1.0" MaskVersion="MV-07B0">
          <Static>
            <Parameters>
              <Parameter Id="M-0083_P-MODE" Name="ChannelMode" Value="1" />
            </Parameters>
            <ParameterRefs>
              <ParameterRef Id="M-0083_PR-MODE" RefId="M-0083_P-MODE" />
            </ParameterRefs>
          </Static>
          <ModuleDefs>
            <ModuleDef Id="M-0083_MD-SWITCH" Name="SwitchModule">
              <Static>
                <Parameters>
                  <Parameter Id="M-0083_P-ONTIME" Name="OnTime" Value="10" />
                </Parameters>
                <ParameterRefs>
                  <ParameterRef Id="M-0083_PR-ONTIME" RefId="M-0083_P-ONTIME" />
                </ParameterRefs>
              </Static>
              <Dynamic>
                <Channel Id="CH-MOD" Text="Kanal {{0}}">
                  <ParameterBlock Id="PB-MOD" Text="Schalten">
                    <ParameterRefRef RefId="M-0083_PR-ONTIME" />
                  </ParameterBlock>
                </Channel>
              </Dynamic>
            </ModuleDef>
          </ModuleDefs>
          <Dynamic>
            <choose ParamRefId="M-0083_PR-MODE">
              <when test="1">
                <Module RefId="M-0083_MD-SWITCH">
                  <TextArg Value="A" />
                </Module>
              </when>
            </choose>
          </Dynamic>
        </ApplicationProgram>
      </ApplicationPrograms>
      <Hardware Id="M-0083_H-99" Name="MOD-01">
        <Products>
          <Product Id="M-0083_PROD-99" OrderNumber="MOD-01.01" Text="Modulares Testgeraet" />
        </Products>
        <Hardware2Programs>
          <Hardware2Program Id="H2P-99" ApplicationProgramRefId="M-0083_A-9999" />
        </Hardware2Programs>
      </Hardware>
    </Manufacturer>
  </ManufacturerData>
</KNX>"""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("M-0083.xml", xml_content.encode("utf-8"))

    parsed = parse_knxprod_bytes(buf.getvalue())
    assert len(parsed.devices) == 1
    dev = parsed.devices[0]
    yaml_data = yaml.safe_load(dev.yaml_content)

    params = yaml_data["parameters"]
    assert len(params) == 2

    # The parameter inside the ModuleDef should have received page and depends_on
    ontime_param = next(p for p in params if p["id"] == "mdt_p-ontime")
    assert ontime_param["page"] == "Kanal A > Schalten"
    assert "depends_on" in ontime_param
    assert ontime_param["depends_on"]["param_id"] == "mdt_p-mode"
    assert ontime_param["depends_on"]["when_values"] == ["1"]
    assert "conditions" not in ontime_param["depends_on"]


def test_multi_level_depends_on_and_multi_value_when_test():
    """Verify that multi-value when tests (e.g. '1 2') are parsed as list and nested chooses have conditions list."""
    xml_content = """<?xml version="1.0" encoding="utf-8"?>
<KNX xmlns="http://knx.org/xml/project/20">
  <ManufacturerData>
    <Manufacturer RefId="M-0083" Name="MDT technologies">
      <ApplicationPrograms>
        <ApplicationProgram Id="M-0083_A-100" Name="Multi Level Test" ApplicationVersion="1.0">
          <Static>
            <Parameters>
              <Parameter Id="M-0083_P-1" Name="P1" Value="1" />
              <Parameter Id="M-0083_P-2" Name="P2" Value="2" />
              <Parameter Id="M-0083_P-3" Name="P3" Value="3" />
            </Parameters>
          </Static>
          <Dynamic>
            <choose ParamRefId="M-0083_P-1">
              <when test="1 2">
                <choose ParamRefId="M-0083_P-2">
                  <when test="3">
                    <ParameterRefRef RefId="M-0083_P-3" />
                  </when>
                </choose>
              </when>
            </choose>
          </Dynamic>
        </ApplicationProgram>
      </ApplicationPrograms>
      <Hardware Id="M-0083_H-1" Name="TEST">
        <Products>
          <Product Id="M-0083_PROD-1" OrderNumber="TEST-01" Text="Test" />
        </Products>
        <Hardware2Programs>
          <Hardware2Program Id="H2P-1" ApplicationProgramRefId="M-0083_A-100" />
        </Hardware2Programs>
      </Hardware>
    </Manufacturer>
  </ManufacturerData>
</KNX>"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("M-0083.xml", xml_content.encode("utf-8"))

    parsed = parse_knxprod_bytes(buf.getvalue())
    dev = parsed.devices[0]
    yaml_data = yaml.safe_load(dev.yaml_content)

    p3 = next(p for p in yaml_data["parameters"] if p["id"] == "mdt_p-3")
    assert "depends_on" in p3
    dep = p3["depends_on"]
    # Immediate parent condition
    assert dep["param_id"] == "mdt_p-2"
    assert dep["when_values"] == ["3"]
    # Nested conditions list present because len(choose_stack) > 1
    assert "conditions" in dep
    assert len(dep["conditions"]) == 2
    assert dep["conditions"][0]["param_id"] == "mdt_p-1"
    # Multi-value split from "1 2"
    assert dep["conditions"][0]["when_values"] == ["1", "2"]
    assert dep["conditions"][1]["param_id"] == "mdt_p-2"
    assert dep["conditions"][1]["when_values"] == ["3"]

    # Test roundtrip parse_konfix_yaml
    reparsed = parse_konfix_yaml(dev.yaml_content)
    rep_p3 = next(p for p in reparsed["parameters"] if p["id"] == "mdt_p-3")
    assert rep_p3["depends_on"]["conditions"][0]["param_id"] == "mdt_p-1"
    assert rep_p3["depends_on"]["conditions"][0]["when_values"] == ["1", "2"]


