import json
from pathlib import Path
from typing import Dict, Tuple, Optional, Any

_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "knx_manufacturers.json"

# In-memory cache of official KNX manufacturers
_MASTER_MANUFACTURERS: Dict[str, Dict[str, Any]] = {}

def _load_master_data():
    global _MASTER_MANUFACTURERS
    if _MASTER_MANUFACTURERS:
        return
    if _DATA_FILE.exists():
        try:
            with open(_DATA_FILE, "r", encoding="utf-8") as f:
                _MASTER_MANUFACTURERS = json.load(f)
        except Exception:
            _MASTER_MANUFACTURERS = {}
    
    # Fallback built-in essentials
    defaults = {
        "M-0083": {"name": "MDT technologies", "knx_manufacturer_id": 131},
        "M-0008": {"name": "GIRA Giersiepen", "knx_manufacturer_id": 8},
        "M-0002": {"name": "ABB", "knx_manufacturer_id": 2},
        "M-0004": {"name": "Albrecht Jung", "knx_manufacturer_id": 4},
        "M-0048": {"name": "Theben AG", "knx_manufacturer_id": 72},
        "M-0001": {"name": "Siemens", "knx_manufacturer_id": 1},
        "M-00C5": {"name": "Weinzierl Engineering GmbH", "knx_manufacturer_id": 197},
        "M-00FA": {"name": "KNX Association", "knx_manufacturer_id": 250},
    }
    for k, v in defaults.items():
        if k not in _MASTER_MANUFACTURERS:
            _MASTER_MANUFACTURERS[k] = v

def register_custom_manufacturer(mfg_id: str, name: str, knx_manufacturer_id: Optional[int] = None):
    """Dynamically register or update a manufacturer in the master cache."""
    _load_master_data()
    _MASTER_MANUFACTURERS[mfg_id] = {
        "name": name,
        "knx_manufacturer_id": knx_manufacturer_id
    }

def resolve_manufacturer(
    mfg_id: str,
    xml_name: Optional[str] = None,
    context_hints: Optional[str] = None
) -> Tuple[str, str]:
    """
    Resolves the official or community manufacturer name.
    
    Priority:
    1. OpenKNX detection:
       - If mfg_id == 'M-00FA' (KNX test ID 250) and context has 'OpenKNX' or no explicit name -> 'OpenKNX'.
       - If context has 'openknx' in any way -> 'OpenKNX'.
    2. Explicit valid name in XML (if name != id and not a generic placeholder).
    3. Official KNX Master Table (610 manufacturers, e.g. M-0083 -> MDT technologies, M-0008 -> GIRA).
    4. Fallback to XML name or 'Hersteller M-xxxx'.
    """
    _load_master_data()
    clean_id = (mfg_id or "M-UNKNOWN").strip().upper()
    hint_lower = (context_hints or "").lower()
    xml_name_clean = (xml_name or "").strip()

    # 1. OpenKNX handling
    if "openknx" in hint_lower or "openknx" in xml_name_clean.lower():
        return clean_id, "OpenKNX"

    if clean_id == "M-00FA":
        # 0x00FA (250) is used by OpenKNX and DIY community
        if xml_name_clean and xml_name_clean.lower() not in ["knx association", "m-00fa"]:
            return clean_id, xml_name_clean
        # By default for modern DIY / open projects using 0x00FA:
        if "open" in hint_lower or "kaenx" in hint_lower:
            return clean_id, "OpenKNX"
        return clean_id, "OpenKNX"

    # 2. Check if XML provided a valid explicit name
    is_generic_name = (
        not xml_name_clean or
        xml_name_clean.upper() == clean_id or
        xml_name_clean.lower() in ["unbekannt", "unknown", "hersteller", "manufacturer"]
    )

    if not is_generic_name:
        return clean_id, xml_name_clean

    # 3. Lookup in KNX Master Manufacturers Database
    if clean_id in _MASTER_MANUFACTURERS:
        official_name = _MASTER_MANUFACTURERS[clean_id].get("name")
        if official_name:
            return clean_id, official_name

    # 4. Fallback
    if xml_name_clean and xml_name_clean.upper() != clean_id:
        return clean_id, xml_name_clean

    return clean_id, f"Hersteller {clean_id}"
