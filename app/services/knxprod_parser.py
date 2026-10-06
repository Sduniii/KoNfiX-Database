import io
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple

from app.services.knx_master_data import resolve_manufacturer, register_custom_manufacturer

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

    # 1. Inspect knx_master.xml if present to enrich master manufacturers cache
    for fname in zf.namelist():
        if fname.lower().endswith("knx_master.xml"):
            try:
                km_root = ET.fromstring(zf.read(fname))
                for elem in km_root.iter():
                    if _strip_ns(elem.tag) == "Manufacturer":
                        mid = elem.attrib.get("Id")
                        mname = elem.attrib.get("Name")
                        kid = elem.attrib.get("KnxManufacturerId")
                        if mid and mname:
                            register_custom_manufacturer(
                                mid, mname, int(kid) if kid and kid.isdigit() else None
                            )
            except Exception:
                pass

    # Find XML files
    xml_files = [f for f in zf.namelist() if f.lower().endswith(".xml") and not f.lower().endswith("knx_master.xml")]
    if not xml_files:
        raise ValueError("Ungültige .knxprod-Datei: Keine XML-Metadatendatei im Archiv gefunden")

    # Detect context hints across all filenames (e.g. OpenKNX detection)
    context_hints = " ".join(zf.namelist())

    # 2. Extract ApplicationPrograms across all XML files in the archive
    app_programs_map: Dict[str, ParsedApplication] = {}
    for f in xml_files:
        try:
            f_root = ET.fromstring(zf.read(f))
            app_nodes = _find_nodes_by_local_name(f_root, "ApplicationProgram")
            for app in app_nodes:
                app_id = app.attrib.get("Id") or app.attrib.get("RefId") or ""
                app_name = app.attrib.get("Name") or app.attrib.get("ProgramName") or app.attrib.get("Text") or "Applikationsprogramm"
                app_version = app.attrib.get("ApplicationVersion") or app.attrib.get("ProgramVersion") or app.attrib.get("Version")
                mask_version = app.attrib.get("MaskVersion")

                com_objs = _find_nodes_by_local_name(app, "ComObject")
                parameters = _find_nodes_by_local_name(app, "Parameter")

                if app_id:
                    app_programs_map[app_id] = ParsedApplication(
                        app_id=app_id,
                        name=app_name,
                        version=app_version,
                        mask_version=mask_version,
                        com_objects_count=len(com_objs),
                        parameters_count=len(parameters),
                    )
        except Exception:
            pass

    # 3. Prioritize Hardware.xml, or M-*.xml
    target_xml = None
    for f in xml_files:
        basename = f.split("/")[-1].upper()
        if "HARDWARE" in basename:
            target_xml = f
            break
    if not target_xml:
        for f in xml_files:
            basename = f.split("/")[-1].upper()
            if basename.startswith("M-") or "MANUFACTURER" in basename or "CATALOG" in basename:
                target_xml = f
                break
    if not target_xml:
        target_xml = xml_files[0]

    xml_bytes = zf.read(target_xml)
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise ValueError(f"Fehler beim Parsen der KNX-XML-Datei '{target_xml}': {e}")

    # Check if target XML content has OpenKNX hints
    if "openknx" in xml_bytes.decode("utf-8", errors="ignore").lower():
        context_hints += " openknx"

    return _parse_knx_xml_root(root, target_xml, app_programs_map, context_hints)

def _parse_knx_xml_root(
    root: ET.Element,
    xml_filename: str,
    app_programs_map: Dict[str, ParsedApplication],
    context_hints: str = ""
) -> ParsedKnxprod:
    # 1. Manufacturer resolution
    mfg_nodes = _find_nodes_by_local_name(root, "Manufacturer")
    raw_mfg_id = "M-UNKNOWN"
    raw_mfg_name = None

    if mfg_nodes:
        mfg_node = mfg_nodes[0]
        raw_mfg_id = mfg_node.attrib.get("RefId") or mfg_node.attrib.get("Id") or raw_mfg_id
        raw_mfg_name = mfg_node.attrib.get("Name") or mfg_node.attrib.get("Text")
    else:
        # Check manufacturer id from filename e.g. M-0083/Hardware.xml or M-00C5.xml
        for part in xml_filename.split("/"):
            if part.upper().startswith("M-"):
                raw_mfg_id = part.split(".")[0].upper()
                break

    # Use comprehensive master data & OpenKNX resolver
    mfg_id, mfg_name = resolve_manufacturer(raw_mfg_id, raw_mfg_name, context_hints)

    # 2. Hardware / Products
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
            if not app_ref:
                # In standard ETS format: <ApplicationProgramRef RefId="M-0083_A-..." />
                for child in h2p:
                    if _strip_ns(child.tag) in ["ApplicationProgramRef", "ApplicationProgram"]:
                        app_ref = child.attrib.get("RefId") or child.attrib.get("Id")
                        if app_ref:
                            break

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


def extract_knxprods_from_zip(content: bytes) -> List[Tuple[str, bytes]]:
    """
    Inspects a ZIP archive and extracts all .knxprod files contained within it
    (including in subfolders).
    Ignores macOS metadata (__MACOSX) and hidden files.
    Returns a list of (filename, bytes).
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        return []

    results: List[Tuple[str, bytes]] = []
    for info in zf.infolist():
        if info.is_dir():
            continue
        fname = info.filename
        parts = fname.replace("\\", "/").split("/")
        basename = parts[-1]
        # Ignore macOS resource fork files, dotfiles, or __MACOSX directories
        if any(p.startswith(".") or p == "__MACOSX" for p in parts):
            continue
        if basename.lower().endswith(".knxprod"):
            try:
                results.append((basename, zf.read(info)))
            except Exception:
                pass

    return results
