import re
from typing import Any, Dict, List, Optional, Tuple
import yaml
from xml.etree import ElementTree as ET


def generate_manufacturer_code(name: Optional[str], legacy_id: Optional[str] = None) -> str:
    """
    Generates a clean, friendly manufacturer slug (e.g. 'openknx', 'mdt', 'gira').
    Eliminates reliance on KNX Association M-xxxx codes. Always lowercase.
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
    slug = slug[:32].rstrip("-")
    return slug or "custom-manufacturer"


def sanitize_id(raw_id: Optional[str], mfg_code: str) -> str:
    """
    Sanitizes any raw KNX XML ID (e.g. 'M-0083_A-1234_P-1', 'M-00FA_UP-1', or 'P-1')
    into a vendor-independent, strictly lowercase identifier:
    Schema: mdt_a-1234_p-1 (always lowercase, prefix with manufacturer code).
    """
    mfg_clean = (mfg_code or "generic").lower().strip()

    if not raw_id:
        return f"{mfg_clean}_item"

    cleaned = str(raw_id).strip()

    # Strip KNX Association manufacturer prefix M-xxxx_ or M-xxxx-
    cleaned = re.sub(r"^M-[0-9a-fA-F]{4}[_-]?", "", cleaned)

    # Strip leading manufacturer code if already prefixed
    if cleaned.lower().startswith(f"{mfg_clean}_") or cleaned.lower().startswith(f"{mfg_clean}-"):
        cleaned = cleaned[len(mfg_clean) + 1:]

    # Convert non-alphanumeric (except hyphen/underscore) to hyphen
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "-", cleaned)
    # Collapse multiple hyphens
    cleaned = re.sub(r"-+", "-", cleaned).strip("-_")

    if not cleaned:
        cleaned = "item"

    return f"{mfg_clean}_{cleaned}".lower()


def _strip_ns(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _get_translation_text(
    ref_id: str,
    translations: Optional[Dict[str, Dict[str, Dict[str, str]]]],
    attr_name: str = "Text"
) -> Tuple[Optional[str], Dict[str, str]]:
    """
    Retrieves prioritized text and available translations for a ref_id.
    Returns: (best_text, {"de": "...", "en": "..."})
    """
    if not translations:
        return None, {}

    ref_map = translations.get(ref_id) or translations.get(ref_id.lower())
    if not ref_map:
        return None, {}

    out_translations: Dict[str, str] = {}
    best_text = None

    # Priority: de-DE -> de -> en-US -> en -> others
    lang_prio = [("de-de", "de"), ("de", "de"), ("en-us", "en"), ("en", "en")]

    for lang_key, text_map in ref_map.items():
        lk = lang_key.lower()
        if attr_name in text_map:
            val = text_map[attr_name].strip()
            if val:
                short_lang = "de" if lk.startswith("de") else ("en" if lk.startswith("en") else lk[:2])
                if short_lang not in out_translations:
                    out_translations[short_lang] = val

    # Pick best text
    for lk, short in lang_prio:
        if lk in ref_map and attr_name in ref_map[lk] and ref_map[lk][attr_name].strip():
            best_text = ref_map[lk][attr_name].strip()
            break

    if not best_text and out_translations:
        best_text = next(iter(out_translations.values()))

    return best_text, out_translations


def extract_dynamic_tree(
    app_node: ET.Element,
    manufacturer_code: str = "generic",
    translations: Optional[Dict[str, Dict[str, Dict[str, str]]]] = None
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Parses the <Dynamic> hierarchy of an ApplicationProgram:
    - Channel, ParameterBlock, ParameterSeparator (hierarchy / pages / sections)
    - choose / when blocks (visibility dependencies)
    - Assign rules (dynamic value assignments)
    Returns:
      (param_dynamic_info, com_object_dynamic_info, assign_rules)
    """
    param_info: Dict[str, Dict[str, Any]] = {}
    co_info: Dict[str, Dict[str, Any]] = {}
    assign_rules: List[Dict[str, Any]] = []

    mfg = (manufacturer_code or "generic").lower()

    # Find <Dynamic> node if present, otherwise iterate app_node directly
    dynamic_nodes = [elem for elem in app_node.iter() if _strip_ns(elem.tag) == "Dynamic"]
    search_root = dynamic_nodes[0] if dynamic_nodes else app_node

    # Helper recursive walker
    def walk(
        node: ET.Element,
        channel_name: Optional[str],
        block_name: Optional[str],
        section_name: Optional[str],
        choose_stack: List[Tuple[str, str]]
    ):
        cur_chan = channel_name
        cur_block = block_name
        cur_sec = section_name

        tag = _strip_ns(node.tag)

        if tag == "Channel":
            ch_id = node.attrib.get("Id", "")
            tr_text, _ = _get_translation_text(ch_id, translations, "Text")
            cur_chan = tr_text or node.attrib.get("Text") or node.attrib.get("Name") or cur_chan
            cur_block = None
            cur_sec = None

        elif tag == "ParameterBlock":
            pb_id = node.attrib.get("Id", "")
            tr_text, _ = _get_translation_text(pb_id, translations, "Text")
            cur_block = tr_text or node.attrib.get("Text") or node.attrib.get("Name") or cur_block
            cur_sec = None

        elif tag == "ParameterSeparator":
            sep_id = node.attrib.get("Id", "")
            tr_text, _ = _get_translation_text(sep_id, translations, "Text")
            cur_sec = tr_text or node.attrib.get("Text") or node.attrib.get("Name") or cur_sec

        elif tag == "ParameterRefRef":
            ref_id = node.attrib.get("RefId") or ""
            if ref_id:
                sanitized_p_id = sanitize_id(ref_id, mfg)
                page = f"{cur_chan} > {cur_block}" if (cur_chan and cur_block) else (cur_chan or cur_block)
                entry = param_info.setdefault(sanitized_p_id, {})
                if page:
                    entry["page"] = page
                if cur_sec:
                    entry["section"] = cur_sec

                if choose_stack:
                    conds = [{"param_id": p_id, "when_values": [val]} for p_id, val in choose_stack]
                    last_pid, last_val = choose_stack[-1]
                    entry["depends_on"] = {
                        "param_id": last_pid,
                        "when_values": [last_val],
                        "conditions": conds
                    }

        elif tag == "ComObjectRefRef":
            ref_id = node.attrib.get("RefId") or ""
            if ref_id:
                sanitized_co_id = sanitize_id(ref_id, mfg)
                entry = co_info.setdefault(sanitized_co_id, {})
                if choose_stack:
                    conds = [{"param_id": p_id, "when_values": [val]} for p_id, val in choose_stack]
                    last_pid, last_val = choose_stack[-1]
                    entry["depends_on"] = {
                        "param_id": last_pid,
                        "when_values": [last_val],
                        "conditions": conds
                    }

        elif tag == "Assign":
            target_ref = node.attrib.get("TargetParamRefRef") or ""
            source_ref = node.attrib.get("SourceParamRefRef") or ""
            val = node.attrib.get("Value")
            if target_ref:
                target_sanitized = sanitize_id(target_ref, mfg)
                source_sanitized = sanitize_id(source_ref, mfg) if source_ref else None
                conds = [{"param_id": p_id, "when_values": [v]} for p_id, v in choose_stack]
                assign_rules.append({
                    "target": target_sanitized,
                    "source": source_sanitized,
                    "value": val,
                    "conditions": conds
                })

        # Process children
        cur_child_sec = cur_sec
        for child in node:
            child_tag = _strip_ns(child.tag)
            if child_tag == "ParameterSeparator":
                sep_id = child.attrib.get("Id", "")
                tr_text, _ = _get_translation_text(sep_id, translations, "Text")
                cur_child_sec = tr_text or child.attrib.get("Text") or child.attrib.get("Name") or cur_child_sec
                continue
            elif child_tag == "choose":
                pref = child.attrib.get("ParamRefId") or ""
                pref_sanitized = sanitize_id(pref, mfg)
                for when_node in child:
                    if _strip_ns(when_node.tag) == "when":
                        test_val = when_node.attrib.get("test", "")
                        new_stack = choose_stack + [(pref_sanitized, test_val)]
                        for grand_child in when_node:
                            walk(grand_child, cur_chan, cur_block, cur_child_sec, new_stack)
            else:
                walk(child, cur_chan, cur_block, cur_child_sec, choose_stack)


    walk(search_root, None, None, None, [])
    return param_info, co_info, assign_rules


def extract_com_objects_from_xml_node(
    app_node: ET.Element,
    manufacturer_code: str = "generic",
    translations: Optional[Dict[str, Dict[str, Dict[str, str]]]] = None,
    dynamic_info: Optional[Dict[str, Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    """
    Extracts all communication objects from an ApplicationProgram XML element,
    resolving translations, dynamic dependencies, and lowercase sanitized IDs.
    """
    com_objects: List[Dict[str, Any]] = []
    mfg = (manufacturer_code or "generic").lower()

    for elem in app_node.iter():
        if _strip_ns(elem.tag) == "ComObject":
            attrib = elem.attrib
            raw_id = attrib.get("Id", "")
            sanitized_id = sanitize_id(raw_id, mfg)

            try:
                raw_num = attrib.get("Number") or raw_id.split("_")[-1]
                num = int(re.sub(r"[^\d]", "", str(raw_num)) or "0")
            except Exception:
                num = len(com_objects)

            # Translation lookups
            tr_text, translations_dict = _get_translation_text(raw_id, translations, "Text")
            tr_func, func_translations = _get_translation_text(raw_id, translations, "FunctionText")

            name = tr_text or attrib.get("Name") or attrib.get("Text") or f"KO {num}"
            func_text = tr_func or attrib.get("FunctionText") or attrib.get("Text") or ""
            dpt = attrib.get("DatapointType") or attrib.get("Dpt") or ""
            size = attrib.get("ObjectSize") or ""

            flags = {
                "communication": attrib.get("CommunicationFlag", "Enabled") != "Disabled",
                "read": attrib.get("ReadFlag", "Disabled") == "Enabled",
                "write": attrib.get("WriteFlag", "Enabled") != "Disabled",
                "transmit": attrib.get("TransmitFlag", "Disabled") == "Enabled",
                "update": attrib.get("UpdateFlag", "Disabled") == "Enabled",
            }

            co_entry: Dict[str, Any] = {
                "id": sanitized_id,
                "number": num,
                "name": name,
                "function": func_text,
                "dpt": dpt,
                "size": size,
                "flags": flags
            }

            if translations_dict or func_translations:
                merged_tr = {}
                for l, t in translations_dict.items():
                    merged_tr[l] = t
                for l, f in func_translations.items():
                    if l not in merged_tr:
                        merged_tr[l] = f
                co_entry["translations"] = merged_tr

            # Check dynamic visibility / conditions
            if dynamic_info and sanitized_id in dynamic_info:
                dyn = dynamic_info[sanitized_id]
                if "depends_on" in dyn:
                    co_entry["depends_on"] = dyn["depends_on"]

            com_objects.append(co_entry)

    com_objects.sort(key=lambda k: k["number"])
    return com_objects


def extract_parameters_from_xml_node(
    app_node: ET.Element,
    manufacturer_code: str = "generic",
    translations: Optional[Dict[str, Dict[str, Dict[str, str]]]] = None,
    dynamic_info: Optional[Dict[str, Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    """
    Extracts all parameters and parameter types from an ApplicationProgram XML element,
    enriching with translations, pages/sections, depends_on, and lowercase IDs.
    """
    mfg = (manufacturer_code or "generic").lower()

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
                    child_id = child.attrib.get("Id") or ""

                    tr_opt_text, opt_tr_dict = _get_translation_text(child_id, translations, "Text")
                    txt = tr_opt_text or child.attrib.get("Text") or child.attrib.get("Name") or str(val)

                    if val is not None:
                        opt_entry: Dict[str, Any] = {"value": str(val), "text": txt}
                        if opt_tr_dict:
                            opt_entry["translations"] = opt_tr_dict
                        options.append(opt_entry)

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
            raw_id = attrib.get("Id") or f"param_{len(parameters)}"
            sanitized_id = sanitize_id(raw_id, mfg)

            if sanitized_id in seen_ids:
                continue
            seen_ids.add(sanitized_id)

            tr_text, tr_dict = _get_translation_text(raw_id, translations, "Text")
            p_name = tr_text or attrib.get("Text") or attrib.get("Name") or sanitized_id
            p_val = attrib.get("Value") or ""
            pt_ref = attrib.get("ParameterTypeRefId") or ""

            pt_info = param_types_map.get(pt_ref, {})
            options = pt_info.get("options", [])

            param_entry: Dict[str, Any] = {
                "id": sanitized_id,
                "name": p_name,
                "text": p_name,
                "default": p_val,
            }

            if tr_dict:
                param_entry["translations"] = tr_dict

            if options:
                param_entry["type"] = "enum"
                param_entry["options"] = options
            else:
                param_entry["type"] = (
                    "number"
                    if (isinstance(p_val, (int, float)) or (isinstance(p_val, str) and p_val.replace(".", "", 1).isdigit()))
                    else "text"
                )

            # Check dynamic tree metadata (page, section, depends_on)
            if dynamic_info and sanitized_id in dynamic_info:
                dyn = dynamic_info[sanitized_id]
                if "page" in dyn:
                    param_entry["page"] = dyn["page"]
                if "section" in dyn:
                    param_entry["section"] = dyn["section"]
                if "depends_on" in dyn:
                    param_entry["depends_on"] = dyn["depends_on"]

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
    assign_rules: Optional[List[Dict[str, Any]]] = None,
    source_url: Optional[str] = None,
) -> str:
    """
    Serializes a full KoNfiX Device Definition into standardized YAML adhering to Schema v1.
    All IDs and slugs strictly lowercase.
    """
    mfg_code_clean = (manufacturer_code or "generic").lower().strip()
    sanitized_app_id = sanitize_id(application_id or f"{mfg_code_clean}_{order_number}", mfg_code_clean)

    doc: Dict[str, Any] = {
        "$schema": "https://konfix.sduni.de/schemas/konfix-device-v1.json",
        "konfix_version": "1.0",
        "manufacturer": {
            "code": mfg_code_clean,
            "name": manufacturer_name,
        },
        "device": {
            "order_number": str(order_number).strip(),
            "name": device_name,
            "description": description or "",
            "hardware": {
                "name": hardware_name or device_name,
                "version": str(hardware_version or "1.0"),
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
            "id": sanitized_app_id,
            "name": application_name or device_name,
            "version": str(application_version or "1.0"),
            "mask_version": mask_version or "MV-07B0",
        }

    doc["communication_objects"] = communication_objects or []
    doc["parameters"] = parameters or []

    if assign_rules:
        doc["assign_rules"] = assign_rules

    return yaml.dump(doc, sort_keys=False, allow_unicode=True, default_flow_style=False)


def parse_konfix_yaml(yaml_content: str) -> Dict[str, Any]:
    """
    Parses and validates a native KoNfiX-YAML device definition string.
    Ensures strict lowercase manufacturer codes and IDs.
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
    raw_code = mfg_data.get("code") or generate_manufacturer_code(mfg_name, legacy_id)
    mfg_code = raw_code.lower().strip()

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
    raw_app_id = app_data.get("id")
    app_id = sanitize_id(raw_app_id, mfg_code) if raw_app_id else f"{mfg_code}_{order_number}".lower()
    app_name = app_data.get("name") or dev_name
    app_version = str(app_data.get("version")) if app_data.get("version") is not None else None
    mask_version = app_data.get("mask_version")

    com_objects = data.get("communication_objects") or []
    parameters = data.get("parameters") or []
    assign_rules = data.get("assign_rules") or []

    # Ensure all IDs inside com_objects and parameters are lowercase
    sanitized_cos = []
    for co in com_objects:
        if isinstance(co, dict):
            c = dict(co)
            if "id" in c:
                c["id"] = sanitize_id(c["id"], mfg_code)
            sanitized_cos.append(c)

    sanitized_params = []
    for p in parameters:
        if isinstance(p, dict):
            p_dict = dict(p)
            if "id" in p_dict:
                p_dict["id"] = sanitize_id(p_dict["id"], mfg_code)
            if "depends_on" in p_dict and isinstance(p_dict["depends_on"], dict):
                dep = dict(p_dict["depends_on"])
                if "param_id" in dep:
                    dep["param_id"] = sanitize_id(dep["param_id"], mfg_code)
                p_dict["depends_on"] = dep
            sanitized_params.append(p_dict)

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
            "com_objects_count": len(sanitized_cos),
            "parameters_count": len(sanitized_params),
        },
        "communication_objects": sanitized_cos,
        "parameters": sanitized_params,
        "assign_rules": assign_rules,
        "raw_yaml": yaml_content
    }
