import io
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class ParsedApplication:
    app_id: str
    name: str
    version: Optional[str] = None
    mask_version: Optional[str] = None
    com_objects_count: int = 0
    parameters_count: int = 0

@dataclass
class ParsedDevice:
    order_number: str
    name: str
    description: Optional[str] = None
    hardware_name: Optional[str] = None
    hardware_version: Optional[str] = None
    bus_current_ma: Optional[float] = None
    applications: List[ParsedApplication] = field(default_factory=list)

@dataclass
class ParsedKnxprod:
    manufacturer_id: str
    manufacturer_name: str
    devices: List[ParsedDevice] = field(default_factory=list)
    raw_xml_filename: Optional[str] = None

def _strip_ns(tag: str) -> str:
    """Strips XML namespace like {http://knx.org/xml/project/20}Tag -> Tag"""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag

def _find_nodes_by_local_name(element: ET.Element, local_name: str) -> List[ET.Element]:
    """Finds all descendant elements matching a local name regardless of namespace."""
    results = []
    for elem in element.iter():
        if _strip_ns(elem.tag) == local_name:
            results.append(elem)
    return results

def parse_knxprod_bytes(content: bytes) -> ParsedKnxprod:
    """
    Extracts XML files from the .knxprod ZIP archive and parses
    manufacturer and device hardware/application data.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as e:
        raise ValueError(f"Ungültiges .knxprod-Format: Keine gültige ZIP-Datei ({e})")

    # Find XML files (usually M-xxxx.xml or project.xml or any .xml)
    xml_files = [f for f in zf.namelist() if f.lower().endswith(".xml")]
    if not xml_files:
        raise ValueError("Ungültige .knxprod-Datei: Keine XML-Metadatendatei im Archiv gefunden")

    # Prioritize M-*.xml
    target_xml = None
    for f in xml_files:
        basename = f.split("/")[-1].upper()
        if basename.startswith("M-") or "MANUFACTURER" in basename or "HARDWARE" in basename:
            target_xml = f
            break
    if not target_xml:
        target_xml = xml_files[0]

    xml_bytes = zf.read(target_xml)
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise ValueError(f"Fehler beim Parsen der KNX-XML-Datei '{target_xml}': {e}")

    return _parse_knx_xml_root(root, target_xml)

def _parse_knx_xml_root(root: ET.Element, xml_filename: str) -> ParsedKnxprod:
    # 1. Manufacturer
    mfg_nodes = _find_nodes_by_local_name(root, "Manufacturer")
    mfg_id = "M-UNKNOWN"
    mfg_name = "Unbekannter Hersteller"

    if mfg_nodes:
        mfg_node = mfg_nodes[0]
        mfg_id = mfg_node.attrib.get("RefId") or mfg_node.attrib.get("Id") or mfg_id
        mfg_name = mfg_node.attrib.get("Name") or mfg_node.attrib.get("Text") or mfg_id
    else:
        # Check manufacturer id from filename e.g. M-00C5.xml
        for part in xml_filename.split("/"):
            if part.upper().startswith("M-"):
                mfg_id = part.split(".")[0].upper()
                mfg_name = f"Hersteller {mfg_id}"
                break

    # 2. Application Programs index by Id
    app_programs_map: Dict[str, ParsedApplication] = {}
    app_nodes = _find_nodes_by_local_name(root, "ApplicationProgram")
    for app in app_nodes:
        app_id = app.attrib.get("Id") or app.attrib.get("RefId") or ""
        app_name = app.attrib.get("Name") or app.attrib.get("ProgramName") or app.attrib.get("Text") or "Applikationsprogramm"
        app_version = app.attrib.get("ApplicationVersion") or app.attrib.get("ProgramVersion") or app.attrib.get("Version")
        mask_version = app.attrib.get("MaskVersion")

        # Count com objects
        com_objs = _find_nodes_by_local_name(app, "ComObject")
        # Count parameters
        parameters = _find_nodes_by_local_name(app, "Parameter")

        parsed_app = ParsedApplication(
            app_id=app_id,
            name=app_name,
            version=app_version,
            mask_version=mask_version,
            com_objects_count=len(com_objs),
            parameters_count=len(parameters),
        )
        if app_id:
            app_programs_map[app_id] = parsed_app

    # 3. Hardware / Products
    devices: List[ParsedDevice] = []
    hardware_nodes = _find_nodes_by_local_name(root, "Hardware")

    for hw in hardware_nodes:
        hw_name = hw.attrib.get("Name") or hw.attrib.get("Text")
        hw_version = hw.attrib.get("VersionNumber") or hw.attrib.get("HardwareVersion")
        bus_current_str = hw.attrib.get("BusCurrent")
        bus_current_ma = None
        if bus_current_str:
            try:
                bus_current_ma = float(bus_current_str)
            except ValueError:
                pass

        # Associated applications for this Hardware
        hw_apps: List[ParsedApplication] = []
        hw2prog_nodes = _find_nodes_by_local_name(hw, "Hardware2Program")
        for h2p in hw2prog_nodes:
            app_ref = h2p.attrib.get("ApplicationProgramRefId")
            if app_ref and app_ref in app_programs_map:
                hw_apps.append(app_programs_map[app_ref])

        # If no explicit hw2prog, link all found apps if only 1 app exists
        if not hw_apps and len(app_programs_map) == 1:
            hw_apps = list(app_programs_map.values())

        # Products under this Hardware
        product_nodes = _find_nodes_by_local_name(hw, "Product")
        if product_nodes:
            for prod in product_nodes:
                order_number = prod.attrib.get("OrderNumber") or prod.attrib.get("Text") or prod.attrib.get("Id")
                prod_name = prod.attrib.get("Text") or prod.attrib.get("Name") or hw_name or order_number
                description = prod.attrib.get("Description")

                if order_number:
                    devices.append(ParsedDevice(
                        order_number=order_number,
                        name=prod_name,
                        description=description,
                        hardware_name=hw_name,
                        hardware_version=hw_version,
                        bus_current_ma=bus_current_ma,
                        applications=hw_apps or list(app_programs_map.values())
                    ))
        else:
            # Fallback if no <Product> sub-element: use hardware itself as product
            serial_or_order = hw.attrib.get("SerialNumber") or hw.attrib.get("OrderNumber") or hw.attrib.get("Id")
            if serial_or_order:
                devices.append(ParsedDevice(
                    order_number=serial_or_order,
                    name=hw_name or serial_or_order,
                    description=None,
                    hardware_name=hw_name,
                    hardware_version=hw_version,
                    bus_current_ma=bus_current_ma,
                    applications=hw_apps or list(app_programs_map.values())
                ))

    # Global Fallback if no Hardware/Products were extracted (e.g. minimalist catalog XML)
    if not devices:
        # Check CatalogItem
        catalog_items = _find_nodes_by_local_name(root, "CatalogItem")
        for ci in catalog_items:
            order_no = ci.attrib.get("Number") or ci.attrib.get("OrderNumber") or ci.attrib.get("Id")
            ci_name = ci.attrib.get("Name") or ci.attrib.get("Text") or order_no
            if order_no:
                devices.append(ParsedDevice(
                    order_number=order_no,
                    name=ci_name,
                    applications=list(app_programs_map.values())
                ))

    # If still empty, create default device from file metadata
    if not devices:
        fallback_order = xml_filename.split("/")[-1].replace(".xml", "")
        devices.append(ParsedDevice(
            order_number=fallback_order,
            name=f"KNX Device ({fallback_order})",
            applications=list(app_programs_map.values())
        ))

    return ParsedKnxprod(
        manufacturer_id=mfg_id,
        manufacturer_name=mfg_name,
        devices=devices,
        raw_xml_filename=xml_filename
    )
