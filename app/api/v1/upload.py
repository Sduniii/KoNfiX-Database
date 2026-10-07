import hashlib
import ipaddress
import logging
import os
import secrets
import socket
from typing import List, Tuple, Union
from urllib.parse import unquote, urlparse

import httpx
from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.api.v1.auth import verify_upload_permission
from app.config import settings
from app.database import get_db
from app.models import (
    ApplicationProgram,
    Device,
    Manufacturer,
    CommunicationObject,
    Parameter,
    AssignRule,
    Translation,
)
from app.schemas.upload import (
    BatchItemResult,
    BatchUploadResponse,
    ImportedApplication,
    ImportedDevice,
    UploadResponse,
    UrlImportRequest,
)
from app.services.knxprod_parser import extract_knxprods_from_zip, parse_knxprod_bytes
from app.services.storage import storage_service, sanitize_filename
from app.services.yaml_converter import parse_konfix_yaml

logger = logging.getLogger(__name__)

DB_GET_DEPENDENCY = Depends(get_db)
FILE_OPEN = File(..., description="Die .knxprod-Datei als Binärdatei (Multipart-Formularfeld 'file')")

router = APIRouter(tags=["Upload (.knxprod)"])


def _validate_safe_url(url_str: str) -> str:
    parsed = urlparse(url_str.strip())
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nur HTTP- und HTTPS-URLs sind erlaubt"
        )
    if not parsed.hostname:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ungültige URL: Kein Hostname gefunden"
        )

    hostname = parsed.hostname.lower()
    if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0", "metadata.google.internal"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Zugriff auf lokale/interne Adressen ist nicht gestattet"
        )

    try:
        addr_info = socket.getaddrinfo(hostname, None)
        for entry in addr_info:
            ip = ipaddress.ip_address(entry[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Zugriff auf private IP-Bereiche ({ip}) ist nicht gestattet"
                )
    except socket.gaierror:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Hostname '{hostname}' konnte nicht aufgelöst werden"
        )

    return url_str.strip()



async def _read_request_body_capped(request: Request, max_bytes: int | None = None) -> bytes:
    limit = max_bytes if max_bytes is not None else settings.MAX_UPLOAD_SIZE_BYTES
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit():
        if int(content_length) > limit:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Upload überschreitet das Limit von {limit // (1024 * 1024) or 1} MB"
            )

    chunks = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > limit:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Upload überschreitet das Limit von {limit // (1024 * 1024) or 1} MB"
            )
        chunks.append(chunk)
    return b"".join(chunks)


async def _read_upload_file_capped(file: UploadFile, max_bytes: int | None = None) -> bytes:
    limit = max_bytes if max_bytes is not None else settings.MAX_UPLOAD_SIZE_BYTES
    chunks = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Datei '{file.filename or 'upload'}' überschreitet das Limit von {limit // (1024 * 1024) or 1} MB"
            )
        chunks.append(chunk)
    return b"".join(chunks)



@router.post(
    "/upload",
    response_model=Union[UploadResponse, BatchUploadResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Upload .knxprod or .zip archive (raw application/octet-stream or multipart)",
    description=(
        "Ultra-einfacher Upload für Hersteller: Sende die rohe .knxprod- oder .zip-Datei direkt als "
        "`application/octet-stream` im Body (optional mit Header `X-File-Name: ...`). "
        "Wird ein .zip-Archiv gesendet, werden alle darin enthaltenen .knxprod-Dateien automatisch "
        "entpackt und importiert. Das Backend parst die KNX-XML-Struktur (M-xxxx.xml) und registriert "
        "Hersteller, Geräte, Applikationen und Metadaten in der Datenbank."
    )
)
async def upload_knxprod(
    request: Request,
    db: Session = DB_GET_DEPENDENCY,
    x_file_name: str | None = Header(None, description="Optionaler Dateiname der .knxprod- oder .zip-Datei"),
    filename: str | None = Query(None, description="Optionaler Dateiname via Query-Parameter"),
    x_source_url: str | None = Header(None, description="Optionale Original-Hersteller-URL (z. B. Download-Link)"),
    source_url: str | None = Query(None, description="Optionale Original-Hersteller-URL via Query-Parameter"),
    _authorized: bool = Depends(verify_upload_permission)
):
    content_type = request.headers.get("content-type", "").lower()
    file_bytes: bytes = b""
    resolved_filename = unquote(x_file_name) if x_file_name else (filename or "device.knxprod")
    resolved_source_url = unquote(x_source_url) if x_source_url else source_url

    if "application/octet-stream" in content_type or not content_type:
        # Raw binary streaming body with size cap
        file_bytes = await _read_request_body_capped(request)
    elif "multipart/form-data" in content_type:
        form = await request.form()
        upload_field = form.get("file")
        if upload_field and hasattr(upload_field, "read"):
            if isinstance(upload_field, UploadFile):
                file_bytes = await _read_upload_file_capped(upload_field)
            else:
                raw_data = await upload_field.read()
                if len(raw_data) > settings.MAX_UPLOAD_SIZE_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Upload überschreitet das Limit von {settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB"
                    )
                file_bytes = raw_data
            if hasattr(upload_field, "filename") and upload_field.filename:
                resolved_filename = upload_field.filename
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formular enthält kein gültiges 'file' Feld"
            )
    else:
        # Fallback: attempt to read raw body anyway (e.g. application/zip, application/x-zip-compressed)
        file_bytes = await _read_request_body_capped(request)

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Keine Dateidaten empfangen. Bitte sende die Binärdaten der .knxprod- oder .zip-Datei."
        )

    # Check for batch ZIP archive containing .knxprod files
    try:
        extracted_knxprods = extract_knxprods_from_zip(file_bytes)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

    if extracted_knxprods:
        return _process_batch_knxprods(extracted_knxprods, db)

    if resolved_filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Das ZIP-Archiv enthält keine gültigen .knxprod-Dateien"
        )

    return _process_single_knxprod(file_bytes, resolved_filename, db, source_url=resolved_source_url)


@router.post(
    "/upload/form",
    response_model=Union[UploadResponse, BatchUploadResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Upload .knxprod or .zip via standard Form Multipart",
    include_in_schema=False
)
async def upload_knxprod_form(
    file: UploadFile = FILE_OPEN,  
    db: Session = DB_GET_DEPENDENCY,
    x_source_url: str | None = Header(None, description="Optionale Original-Hersteller-URL (z. B. Download-Link)"),
    source_url: str | None = Query(None, description="Optionale Original-Hersteller-URL via Query-Parameter"),
    _authorized: bool = Depends(verify_upload_permission)
):
    content = await _read_upload_file_capped(file)
    fname = file.filename or "device.knxprod"
    resolved_source_url = unquote(x_source_url) if x_source_url else source_url
    try:
        extracted_knxprods = extract_knxprods_from_zip(content)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

    if extracted_knxprods:
        return _process_batch_knxprods(extracted_knxprods, db)

    if fname.lower().endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Das ZIP-Archiv enthält keine gültigen .knxprod-Dateien"
        )

    return _process_single_knxprod(content, fname, db, source_url=resolved_source_url)


@router.post(
    "/upload/url",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import .knxprod from official manufacturer URL (Metadata-only or Cached)",
    description="Lädt eine .knxprod-Datei von einer offiziellen Hersteller-URL herunter, extrahiert die XML-Metadaten und speichert die source_url für 302-Redirects."
)
async def upload_knxprod_from_url(
    payload: UrlImportRequest,
    db: Session = DB_GET_DEPENDENCY,
    _authorized: bool = Depends(verify_upload_permission)
):
    safe_url = _validate_safe_url(payload.url)
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            async with client.stream("GET", safe_url) as resp:
                if resp.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Hersteller-Server antwortete mit HTTP {resp.status_code}"
                    )

                fname = payload.filename
                if not fname:
                    cd = resp.headers.get("content-disposition", "")
                    if "filename=" in cd:
                        fname = cd.split("filename=")[-1].strip('"\' ')
                    else:
                        fname = os.path.basename(urlparse(safe_url).path) or "download.knxprod"
                if not fname.lower().endswith(".knxprod"):
                    fname += ".knxprod"

                chunks = []
                total = 0
                limit = settings.MAX_UPLOAD_SIZE_BYTES
                async for chunk in resp.aiter_bytes(chunk_size=64 * 1024):
                    total += len(chunk)
                    if total > limit:
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"Datei von URL überschreitet das Limit von {limit // (1024 * 1024)} MB"
                        )
                    chunks.append(chunk)
                content = b"".join(chunks)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Fehler beim Abruf von Hersteller-URL: {exc!s}"
        )

    return _process_single_knxprod(
        content,
        fname,
        db,
        source_url=safe_url,
        store_binary=payload.store_binary
    )


@router.post(
    "/upload/batch",
    response_model=BatchUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload multiple .knxprod or .zip files via multipart/form-data",
    description=(
        "Ermöglicht den gleichzeitigen Upload mehrerer .knxprod- und/oder .zip-Dateien. "
        "ZIP-Archive werden automatisch entpackt. Alle enthaltenen .knxprod-Dateien werden "
        "importiert und indexiert."
    )
)
async def upload_knxprod_batch(
    files: List[UploadFile] = File(..., description="Eine oder mehrere .knxprod- oder .zip-Dateien"),
    db: Session = DB_GET_DEPENDENCY,
    _authorized: bool = Depends(verify_upload_permission)
):
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Keine Dateien zum Upload übergeben"
        )

    items_to_process: List[Tuple[str, bytes]] = []
    failed_items: List[BatchItemResult] = []

    for f in files:
        fname = f.filename or "unknown.knxprod"
        try:
            content = await _read_upload_file_capped(f)
        except HTTPException as he:
            failed_items.append(BatchItemResult(
                filename=fname,
                status="error",
                message=he.detail,
                devices_imported=[]
            ))
            continue

        if not content:
            failed_items.append(BatchItemResult(
                filename=fname,
                status="error",
                message="Datei ist leer",
                devices_imported=[]
            ))
            continue

        try:
            extracted = extract_knxprods_from_zip(content)
        except ValueError as ve:
            failed_items.append(BatchItemResult(
                filename=fname,
                status="error",
                message=str(ve),
                devices_imported=[]
            ))
            continue

        if extracted:
            items_to_process.extend(extracted)
        elif fname.lower().endswith(".zip"):
            failed_items.append(BatchItemResult(
                filename=fname,
                status="error",
                message="ZIP-Archiv enthält keine .knxprod-Dateien",
                devices_imported=[]
            ))
        else:
            items_to_process.append((fname, content))

    batch_resp = _process_batch_knxprods(items_to_process, db)
    if failed_items:
        batch_resp.results.extend(failed_items)
        batch_resp.failed_count += len(failed_items)
        batch_resp.total_files += len(failed_items)
        if batch_resp.successful_count == 0:
            batch_resp.status = "error"
        else:
            batch_resp.status = "partial"
        batch_resp.message = (
            f"{batch_resp.successful_count} von {batch_resp.total_files} Dateien "
            f"erfolgreich importiert ({batch_resp.failed_count} fehlgeschlagen)"
        )

    return batch_resp


def _is_yaml(file_bytes: bytes, filename: str) -> bool:
    if filename.lower().endswith((".yaml", ".yml")):
        return True
    try:
        decoded = file_bytes[:1024].decode("utf-8", errors="ignore").lstrip()
        if decoded.startswith("---") or "konfix_version:" in decoded or "device:" in decoded:
            return True
    except Exception:
        pass
    return False


def _sync_device_records(
    db: Session,
    device: Device,
    parsed_yaml_data: dict
):
    # Remove previous children for fresh sync
    db.query(CommunicationObject).filter(CommunicationObject.device_id == device.id).delete()
    db.query(Parameter).filter(Parameter.device_id == device.id).delete()
    db.query(AssignRule).filter(AssignRule.device_id == device.id).delete()
    db.query(Translation).filter(Translation.device_id == device.id).delete()
    db.flush()

    # 1. Communication Objects
    for co in parsed_yaml_data.get("communication_objects") or []:
        co_rec = CommunicationObject(
            device_id=device.id,
            obj_id=co.get("id") or f"{device.order_number}_o-{co.get('number', 0)}",
            number=co.get("number", 0),
            name=co.get("name"),
            function=co.get("function"),
            dpt=co.get("dpt"),
            size=co.get("size"),
            flags=co.get("flags"),
            conditions=co.get("conditions")
        )
        db.add(co_rec)

    # 2. Parameters
    for idx, p in enumerate(parsed_yaml_data.get("parameters") or []):
        p_rec = Parameter(
            device_id=device.id,
            param_id=p.get("id") or f"{device.order_number}_p-{idx + 1}",
            name=p.get("name") or "",
            text=p.get("text"),
            type=p.get("type"),
            default_value=str(p.get("default")) if p.get("default") is not None else None,
            page=p.get("page"),
            section=p.get("section"),
            options=p.get("options"),
            conditions=p.get("conditions")
        )
        db.add(p_rec)

    # 3. Assign Rules
    for ar in parsed_yaml_data.get("assign_rules") or []:
        ar_rec = AssignRule(
            device_id=device.id,
            target=ar.get("target"),
            source=ar.get("source"),
            value=ar.get("value"),
            conditions=ar.get("conditions")
        )
        db.add(ar_rec)

    # 4. Translations
    tr_dict = parsed_yaml_data.get("translations") or {}
    for entity_id, lang_dict in tr_dict.items():
        if isinstance(lang_dict, dict):
            for lang, text_val in lang_dict.items():
                tr_rec = Translation(
                    device_id=device.id,
                    entity_id=entity_id,
                    language=lang,
                    text=str(text_val)
                )
                db.add(tr_rec)
    db.flush()


def _save_yaml_db(
    file_bytes: bytes,
    filename: str,
    db: Session,
    source_url: str | None = None
) -> UploadResponse:
    try:
        yaml_str = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("YAML-Datei konnte nicht als UTF-8 dekodiert werden")

    try:
        parsed = parse_konfix_yaml(yaml_str)
    except ValueError as e:
        raise ValueError(f"Fehler bei der KoNfiX-YAML-Verarbeitung: {e!s}")

    mfg_info = parsed["manufacturer"]
    mfg_code = mfg_info.get("code") or "custom-manufacturer"
    mfg_name = mfg_info.get("name") or "Unbekannter Hersteller"
    legacy_knx_id = mfg_info.get("legacy_knx_id")

    # 1. Manufacturer
    manufacturer = None
    if mfg_code:
        manufacturer = db.query(Manufacturer).filter(Manufacturer.code == mfg_code).first()
    if not manufacturer and legacy_knx_id:
        manufacturer = db.query(Manufacturer).filter(Manufacturer.knx_id == legacy_knx_id).first()

    if not manufacturer:
        manufacturer = Manufacturer(
            code=mfg_code,
            name=mfg_name,
            knx_id=legacy_knx_id
        )
        db.add(manufacturer)
        db.flush()
    else:
        if mfg_code and not manufacturer.code:
            manufacturer.code = mfg_code
        if mfg_name and not manufacturer.name:
            manufacturer.name = mfg_name
        if legacy_knx_id and not manufacturer.knx_id:
            manufacturer.knx_id = legacy_knx_id
        db.flush()

    dev_info = parsed["device"]
    order_number = dev_info["order_number"]

    # 2. Store YAML file in catalog_files
    clean_filename = sanitize_filename(filename or f"{order_number}.yaml")
    if not clean_filename.lower().endswith((".yaml", ".yml")):
        clean_filename += ".yaml"
    storage_service.save_yaml_content(yaml_str, clean_filename)
    sha256_hash = hashlib.sha256(file_bytes).hexdigest()
    file_size = len(file_bytes)

    # 3. Device
    resolved_source_url = source_url or dev_info.get("source_url")
    device = db.query(Device).filter(Device.order_number == order_number).first()
    if not device:
        device = Device(
            order_number=order_number,
            name=dev_info.get("name") or order_number,
            description=dev_info.get("description"),
            hardware_name=dev_info.get("hardware_name"),
            hardware_version=dev_info.get("hardware_version"),
            bus_current_ma=dev_info.get("bus_current_ma"),
            source_url=resolved_source_url,
            manufacturer_id=manufacturer.id,
            yaml_content=yaml_str
        )
        db.add(device)
        db.flush()
    else:
        device.name = dev_info.get("name") or device.name
        device.description = dev_info.get("description") or device.description
        device.hardware_name = dev_info.get("hardware_name") or device.hardware_name
        device.hardware_version = dev_info.get("hardware_version") or device.hardware_version
        device.bus_current_ma = dev_info.get("bus_current_ma") or device.bus_current_ma
        device.source_url = resolved_source_url or device.source_url
        device.manufacturer_id = manufacturer.id
        device.yaml_content = yaml_str
        db.query(ApplicationProgram).filter(ApplicationProgram.device_id == device.id).delete()
        db.flush()

    # 4. Application
    app_info = parsed.get("application") or {}
    app_rec = ApplicationProgram(
        device_id=device.id,
        app_id=app_info.get("id") or f"{mfg_code}_{order_number}",
        name=app_info.get("name") or device.name,
        version=app_info.get("version"),
        mask_version=app_info.get("mask_version"),
        com_objects_count=app_info.get("com_objects_count", len(parsed.get("communication_objects", []))),
        parameters_count=app_info.get("parameters_count", len(parsed.get("parameters", [])))
    )
    db.add(app_rec)
    db.flush()

    # 5. Populate relational children
    _sync_device_records(db, device, parsed)

    app_responses = [ImportedApplication(
        name=app_rec.name,
        version=app_rec.version,
        mask_version=app_rec.mask_version,
        com_objects_count=app_rec.com_objects_count,
        parameters_count=app_rec.parameters_count
    )]

    imported_devices_resp = [ImportedDevice(
        order_number=device.order_number,
        name=device.name,
        hardware_version=device.hardware_version,
        bus_current_ma=device.bus_current_ma,
        applications=app_responses
    )]

    return UploadResponse(
        status="success",
        message="KoNfiX-YAML-Gerätedefinition erfolgreich empfangen und relational indexiert",
        filename=clean_filename,
        file_size_bytes=file_size,
        sha256=sha256_hash,
        source_url=device.source_url,
        manufacturer_id=manufacturer.knx_id or manufacturer.code or "unknown",
        manufacturer_name=manufacturer.name,
        manufacturer_code=manufacturer.code,
        devices_imported=imported_devices_resp
    )


def _save_knxprod_db(
    file_bytes: bytes,
    filename: str,
    db: Session,
    source_url: str | None = None,
    store_binary: bool = True
) -> UploadResponse:
    # 1. Parse XML and validate ZIP structure in memory
    try:
        parsed = parse_knxprod_bytes(file_bytes)
    except ValueError as e:
        raise ValueError(f"Fehler bei der KNXProd-Verarbeitung: {e!s}")

    sha256_hash = hashlib.sha256(file_bytes).hexdigest()
    file_size = len(file_bytes)

    # 2. Check or create Manufacturer
    manufacturer = None
    if parsed.manufacturer_code:
        manufacturer = db.query(Manufacturer).filter(Manufacturer.code == parsed.manufacturer_code).first()
    if not manufacturer and parsed.manufacturer_id:
        manufacturer = db.query(Manufacturer).filter(Manufacturer.knx_id == parsed.manufacturer_id).first()

    if not manufacturer:
        manufacturer = Manufacturer(
            knx_id=parsed.manufacturer_id,
            name=parsed.manufacturer_name,
            code=parsed.manufacturer_code
        )
        db.add(manufacturer)
        db.flush()
    else:
        if parsed.manufacturer_code and not manufacturer.code:
            manufacturer.code = parsed.manufacturer_code
        if parsed.manufacturer_name and not manufacturer.name:
            manufacturer.name = parsed.manufacturer_name
        if parsed.manufacturer_id and not manufacturer.knx_id:
            manufacturer.knx_id = parsed.manufacturer_id
        db.flush()

    # 3. Insert / Update Devices, Applications, and Relational Children
    imported_devices_resp = []

    for d in parsed.devices:
        device = db.query(Device).filter(Device.order_number == d.order_number).first()
        if not device:
            device = Device(
                order_number=d.order_number,
                name=d.name,
                description=d.description,
                hardware_name=d.hardware_name,
                hardware_version=d.hardware_version,
                bus_current_ma=d.bus_current_ma,
                source_url=source_url,
                manufacturer_id=manufacturer.id,
                yaml_content=d.yaml_content
            )
            db.add(device)
            db.flush()
        else:
            device.name = d.name or device.name
            device.description = d.description or device.description
            device.hardware_name = d.hardware_name or device.hardware_name
            device.hardware_version = d.hardware_version or device.hardware_version
            device.bus_current_ma = d.bus_current_ma or device.bus_current_ma
            device.source_url = source_url or device.source_url
            device.manufacturer_id = manufacturer.id
            device.yaml_content = d.yaml_content
            db.query(ApplicationProgram).filter(ApplicationProgram.device_id == device.id).delete()
            db.flush()

        app_responses = []
        for app in d.applications:
            app_rec = ApplicationProgram(
                device_id=device.id,
                app_id=app.app_id,
                name=app.name,
                version=app.version,
                mask_version=app.mask_version,
                com_objects_count=app.com_objects_count,
                parameters_count=app.parameters_count
            )
            db.add(app_rec)
            app_responses.append(ImportedApplication(
                name=app.name,
                version=app.version,
                mask_version=app.mask_version,
                com_objects_count=app.com_objects_count,
                parameters_count=app.parameters_count
            ))

        # Parse generated KoNfiX-YAML and populate relational records
        if d.yaml_content:
            try:
                parsed_d_yaml = parse_konfix_yaml(d.yaml_content)
                _sync_device_records(db, device, parsed_d_yaml)
            except Exception:
                pass
            # Save YAML file in catalog_files
            storage_service.save_yaml_content(d.yaml_content, f"{d.order_number}.yaml")

        imported_devices_resp.append(ImportedDevice(
            order_number=device.order_number,
            name=device.name,
            hardware_version=device.hardware_version,
            bus_current_ma=device.bus_current_ma,
            applications=app_responses
        ))

    db.flush()

    return UploadResponse(
        status="success",
        message="KNXProd-Datei erfolgreich empfangen, in KoNfiX relational konvertiert und indexiert",
        filename=sanitize_filename(filename),
        file_size_bytes=file_size,
        sha256=sha256_hash,
        source_url=source_url,
        manufacturer_id=manufacturer.knx_id or manufacturer.code or "unknown",
        manufacturer_name=manufacturer.name,
        manufacturer_code=manufacturer.code,
        devices_imported=imported_devices_resp
    )


def _process_single_knxprod(
    file_bytes: bytes,
    filename: str,
    db: Session,
    source_url: str | None = None,
    store_binary: bool = True
) -> UploadResponse:
    try:
        if _is_yaml(file_bytes, filename):
            resp = _save_yaml_db(
                file_bytes,
                filename,
                db,
                source_url=source_url
            )
        else:
            resp = _save_knxprod_db(
                file_bytes,
                filename,
                db,
                source_url=source_url,
                store_binary=store_binary
            )
        db.commit()
        return resp
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Fehler bei der KNXProd-Verarbeitung: {e!s}"
        )
    except Exception as e:
        db.rollback()
        logger.exception("Interner Fehler beim Verarbeiten und Speichern: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Interner Serverfehler beim Verarbeiten der Datei"
        )


# Abwaertskompatibilitaet fuer Skripte und Seeds
_process_and_save_knxprod = _process_single_knxprod


def _process_batch_knxprods(files: List[Tuple[str, bytes]], db: Session) -> BatchUploadResponse:
    results: List[BatchItemResult] = []
    success_count = 0
    fail_count = 0

    for fname, fbytes in files:
        savepoint = db.begin_nested()
        try:
            if _is_yaml(fbytes, fname):
                resp = _save_yaml_db(fbytes, fname, db)
            else:
                resp = _save_knxprod_db(fbytes, fname, db)
            savepoint.commit()
            success_count += 1
            results.append(BatchItemResult(
                filename=resp.filename,
                status="success",
                message="Erfolgreich importiert",
                file_size_bytes=resp.file_size_bytes,
                sha256=resp.sha256,
                source_url=resp.source_url,
                manufacturer_id=resp.manufacturer_id,
                manufacturer_name=resp.manufacturer_name,
                manufacturer_code=resp.manufacturer_code,
                devices_imported=resp.devices_imported
            ))
        except Exception as e:
            savepoint.rollback()
            fail_count += 1
            results.append(BatchItemResult(
                filename=os.path.basename(fname),
                status="error",
                message=str(e),
                devices_imported=[]
            ))

    if success_count > 0:
        db.commit()

    total = len(files)
    batch_status = "success" if fail_count == 0 else ("partial" if success_count > 0 else "error")
    msg = f"{success_count} von {total} Dateien erfolgreich importiert"
    if fail_count > 0:
        msg += f" ({fail_count} fehlgeschlagen)"

    return BatchUploadResponse(
        status=batch_status,
        message=msg,
        total_files=total,
        successful_count=success_count,
        failed_count=fail_count,
        results=results
    )

