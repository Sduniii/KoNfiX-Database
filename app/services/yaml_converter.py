import re
from typing import Any, Dict, List, Optional
import yaml
from xml.etree import ElementTree as ET


def generate_manufacturer_code(name: Optional[str], legacy_id: Optional[str] = None) -> str:
    """
    Generates a clean, friendly manufacturer slug (e.g. 'openknx', 'mdt', 'gira').
    Eliminates reliance on KNX Association M-xxxx codes.
    """
    KNOWN_SLUGS = {
        "m-00fa": "openknx",
        "m-0083": "mdt",
        "m-00c5": "mdt",
        "m-0008": "gira",
        "m-0002": "abb",
        "m-0048": "theben",
        "m-0004": "jung",
        "m-0001": "siemens",
        "m-0077": "theben",
    }

    if legacy_id and legacy_id.lower() in KNOWN_SLUGS:
        return KNOWN_SLUGS[legacy_id.lower()]

    if not name or not name.strip():
        if legacy_id:
            cleaned_legacy = re.sub(r"[^a-z0-9_-]", "", legacy_id.lower())
            return cleaned_legacy or "custom-manufacturer"
        return "custom-manufacturer"

    name_lower = name.lower().strip()

    # Match common well-known brands
    if "openknx" in name_lower:
        return "openknx"
    if "mdt" in name_lower:
        return "mdt"
    if "gira" in name_lower:
        return "gira"
    if "abb" in name_lower:
        return "abb"
    if "theben" in name_lower:
        return "theben"
    if "jung" in name_lower:
        return "jung"
    if "siemens" in name_lower:
        return "siemens"

    # General slugification
    slug = re.sub(r"[^a-z0-9]+", "-", name_lower).strip("-")
    # Truncate clean slug
    slug = slug[:32].rstrip("-")
    return slug or "custom-manufacturer"


def _strip_ns(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def extract_com_objects_from_xml_node(app_node: ET.Element) -> List[Dict[str, Any]]:
    """
    Extracts all communication objects from an ApplicationProgram XML element.
    """
    com_objects: List[Dict[str, Any]] = []

    for elem in app_node.iter():
        if _strip_ns(elem.tag) == "ComObject":
            attrib = elem.attrib
            try:
                raw_num = attrib.get("Number") or attrib.get("Id", "0").split("_")[-1]
                num = int(re.sub(r"[^\d]", "", str(raw_num)) or "0")
            except Exception:
                num = len(com_objects)

            name = attrib.get("Name") or f"KO {num}"
            func_text = attrib.get("Text") or attrib.get("FunctionText") or ""
            dpt = attrib.get("DatapointType") or attrib.get("Dpt") or ""
            size = attrib.get("ObjectSize") or ""

            # Standard KNX flags
            flags = {
                "communication": attrib.get("CommunicationFlag", "Enabled") != "Disabled",
                "read": attrib.get("ReadFlag", "Disabled") == "Enabled",
                "write": attrib.get("WriteFlag", "Enabled") != "Disabled",
                "transmit": attrib.get("TransmitFlag", "Disabled") == "Enabled",
                "update": attrib.get("UpdateFlag", "Disabled") == "Enabled",
            }

            com_objects.append({
                "number": num,
                "name": name,
                "function": func_text,
                "dpt": dpt,
                "size": size,
                "flags": flags
            })

    # Sort stably by KO number
    com_objects.sort(key=lambda k: k["number"])
    return com_objects


def extract_parameters_from_xml_node(app_node: ET.Element) -> List[Dict[str, Any]]:
    """
    Extracts all parameters and parameter types from an ApplicationProgram XML element.
    """
    # 1. Map ParameterTypes
    param_types_map: Dict[str, Dict[str, Any]] = {}
    for elem in app_node.iter():
        if _strip_ns(elem.tag) == "ParameterType":
            pt_id = elem.attrib.get("Id") or ""
            pt_name = elem.attrib.get("Name") or ""
            options = []

            for child in elem.iter():
                if _strip_ns(child.tag) in ["Enumeration", "TypeRestriction"]:
                    val = child.attrib.get("Value")
                    txt = child.attrib.get("Text") or child.attrib.get("Name") or str(val)
                    if val is not None:
                        options.append({"value": val, "text": txt})

            param_types_map[pt_id] = {
                "name": pt_name,
                "options": options,
            }

    # 2. Extract Parameters
    parameters: List[Dict[str, Any]] = []
    seen_ids = set()

    for elem in app_node.iter():
        if _strip_ns(elem.tag) == "Parameter":
            attrib = elem.attrib
            p_id = attrib.get("Id") or f"param_{len(parameters)}"
            if p_id in seen_ids:
                continue
            seen_ids.add(p_id)

            p_name = attrib.get("Name") or attrib.get("Text") or p_id
            p_val = attrib.get("Value") or ""
            pt_ref = attrib.get("ParameterTypeRefId") or ""

            pt_info = param_types_map.get(pt_ref, {})
            options = pt_info.get("options", [])

            param_entry: Dict[str, Any] = {
                "id": p_id,
                "name": p_name,
                "default": p_val,
            }

            if options:
                param_entry["type"] = "enum"
                param_entry["options"] = options
            else:
                param_entry["type"] = "number" if (isinstance(p_val, (int, float)) or (isinstance(p_val, str) and p_val.replace(".", "", 1).isdigit())) else "text"

            parameters.append(param_entry)

    return parameters


def build_konfix_yaml(
    manufacturer_code: str,
    manufacturer_name: str,
    legacy_knx_id: Optional[str],
    order_number: str,
    device_name: str,
    description: Optional[str] = None,
    hardware_name: Optional[str] = None,
    hardware_version: Optional[str] = None,
    bus_current_ma: Optional[float] = None,
    application_id: Optional[str] = None,
    application_name: Optional[str] = None,
    application_version: Optional[str] = None,
    mask_version: Optional[str] = None,
    communication_objects: Optional[List[Dict[str, Any]]] = None,
    parameters: Optional[List[Dict[str, Any]]] = None,
    source_url: Optional[str] = None,
) -> str:
    """
    Serializes a full KoNfiX Device Definition into standardized YAML.
    """
    doc: Dict[str, Any] = {
        "konfix_version": "1.0",
        "manufacturer": {
            "code": manufacturer_code,
            "name": manufacturer_name,
        },
        "device": {
            "order_number": order_number,
            "name": device_name,
            "description": description or "",
            "hardware": {
                "name": hardware_name or device_name,
                "version": hardware_version or "1.0",
                "bus_current_ma": bus_current_ma or 10.0,
            }
        }
    }

    if legacy_knx_id:
        doc["manufacturer"]["legacy_knx_id"] = legacy_knx_id
    if source_url:
        doc["device"]["source_url"] = source_url

    if application_name or application_id:
        doc["application"] = {
            "id": application_id or f"{manufacturer_code}_{order_number}",
            "name": application_name or device_name,
            "version": application_version or "1.0",
            "mask_version": mask_version or "MV-07B0",
        }

    doc["communication_objects"] = communication_objects or []
    doc["parameters"] = parameters or []

    return yaml.dump(doc, sort_keys=False, allow_unicode=True, default_flow_style=False)


def parse_konfix_yaml(yaml_content: str) -> Dict[str, Any]:
    """
    Parses and validates a native KoNfiX-YAML device definition string.
    """
    try:
        data = yaml.safe_load(yaml_content)
    except Exception as e:
        raise ValueError(f"Ungültiges YAML-Format: {e}")

    if not isinstance(data, dict):
        raise ValueError("YAML-Inhalt muss ein Mapping/Dictionary auf oberster Ebene sein.")

    mfg_data = data.get("manufacturer") or {}
    dev_data = data.get("device") or {}

    mfg_name = mfg_data.get("name") or "Unbekannter Hersteller"
    legacy_id = mfg_data.get("legacy_knx_id") or mfg_data.get("knx_id")
    mfg_code = mfg_data.get("code") or generate_manufacturer_code(mfg_name, legacy_id)

    order_number = dev_data.get("order_number")
    if not order_number:
        raise ValueError("Das Feld 'device.order_number' ist im KoNfiX-YAML zwingend erforderlich.")

    dev_name = dev_data.get("name") or order_number
    description = dev_data.get("description")
    hw_data = dev_data.get("hardware") or {}
    hw_name = hw_data.get("name")
    hw_version = str(hw_data.get("version")) if hw_data.get("version") is not None else None
    bus_current = hw_data.get("bus_current_ma")

    app_data = data.get("application") or {}
    app_id = app_data.get("id")
    app_name = app_data.get("name") or dev_name
    app_version = str(app_data.get("version")) if app_data.get("version") is not None else None
    mask_version = app_data.get("mask_version")

    com_objects = data.get("communication_objects") or []
    parameters = data.get("parameters") or []

    return {
        "manufacturer": {
            "code": mfg_code,
            "name": mfg_name,
            "legacy_knx_id": legacy_id,
        },
        "device": {
            "order_number": str(order_number).strip(),
            "name": dev_name,
            "description": description,
            "hardware_name": hw_name,
            "hardware_version": hw_version,
            "bus_current_ma": float(bus_current) if bus_current is not None else None,
            "source_url": dev_data.get("source_url"),
        },
        "application": {
            "id": app_id,
            "name": app_name,
            "version": app_version,
            "mask_version": mask_version,
            "com_objects_count": len(com_objects),
            "parameters_count": len(parameters),
        },
        "communication_objects": com_objects,
        "parameters": parameters,
        "raw_yaml": yaml_content
    }
