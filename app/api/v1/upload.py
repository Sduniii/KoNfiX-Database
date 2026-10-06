import logging
import os
import secrets
from typing import List, Tuple, Union
from urllib.parse import unquote

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

from app.config import settings
from app.database import get_db
from app.models import ApplicationProgram, Device, KnxprodFile, Manufacturer
from app.schemas.upload import (
    BatchItemResult,
    BatchUploadResponse,
    ImportedApplication,
    ImportedDevice,
    UploadResponse,
)
from app.services.knxprod_parser import extract_knxprods_from_zip, parse_knxprod_bytes
from app.services.storage import storage_service

logger = logging.getLogger(__name__)

DB_GET_DEPENDENCY = Depends(get_db)
FILE_OPEN = File(..., description="Die .knxprod-Datei als Binärdatei (Multipart-Formularfeld 'file')")

router = APIRouter(tags=["Upload (.knxprod)"])

def verify_api_key(
    x_api_key: str | None = Header(None),
    authorization: str | None = Header(None)
):
    if not settings.API_KEY:
        return True

    token = x_api_key
    if not token and authorization:
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
        else:
            token = authorization.strip()

    if not token or not secrets.compare_digest(token, settings.API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungültiger oder fehlender API-Key (Header 'X-API-Key' oder 'Authorization: Bearer <token>')"
        )
    return True


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
    _authorized: bool = Depends(verify_api_key)
):
    content_type = request.headers.get("content-type", "").lower()
    file_bytes: bytes = b""
    resolved_filename = unquote(x_file_name) if x_file_name else (filename or "device.knxprod")

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

    return _process_single_knxprod(file_bytes, resolved_filename, db)


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
    _authorized: bool = Depends(verify_api_key)
):
    content = await _read_upload_file_capped(file)
    fname = file.filename or "device.knxprod"
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

    return _process_single_knxprod(content, fname, db)



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
    _authorized: bool = Depends(verify_api_key)
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


def _save_knxprod_db(file_bytes: bytes, filename: str, db: Session) -> UploadResponse:
    # 1. Parse XML and validate ZIP structure
    try:
        parsed = parse_knxprod_bytes(file_bytes)
    except ValueError as e:
        raise ValueError(f"Fehler bei der KNXProd-Verarbeitung: {e!s}")

    # 2. Store binary file
    stored_path, sha256_hash, file_size = storage_service.save_knxprod_bytes(file_bytes, filename)

    # 3. Check or create KnxprodFile record
    knx_file_rec = db.query(KnxprodFile).filter(KnxprodFile.sha256 == sha256_hash).first()
    if not knx_file_rec:
        from app.services.storage import sanitize_filename
        knx_file_rec = KnxprodFile(
            filename=sanitize_filename(filename),
            file_size_bytes=file_size,
            sha256=sha256_hash,
            storage_path=stored_path,
            mime_type="application/octet-stream"
        )
        db.add(knx_file_rec)
        db.flush()

    # 4. Check or create Manufacturer
    manufacturer = db.query(Manufacturer).filter(Manufacturer.knx_id == parsed.manufacturer_id).first()
    if not manufacturer:
        manufacturer = Manufacturer(
            knx_id=parsed.manufacturer_id,
            name=parsed.manufacturer_name
        )
        db.add(manufacturer)
        db.flush()
    else:
        # Update name if previously generic
        if parsed.manufacturer_name and not manufacturer.name:
            manufacturer.name = parsed.manufacturer_name

    # 5. Insert / Update Devices and Applications
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
                manufacturer_id=manufacturer.id,
                knxprod_file_id=knx_file_rec.id
            )
            db.add(device)
            db.flush()
        else:
            device.name = d.name or device.name
            device.description = d.description or device.description
            device.hardware_name = d.hardware_name or device.hardware_name
            device.hardware_version = d.hardware_version or device.hardware_version
            device.bus_current_ma = d.bus_current_ma or device.bus_current_ma
            device.knxprod_file_id = knx_file_rec.id
            # Remove previous applications for fresh sync
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
        message="KNXProd-Datei erfolgreich empfangen, geparst und indexiert",
        filename=knx_file_rec.filename,
        file_size_bytes=file_size,
        sha256=sha256_hash,
        manufacturer_id=manufacturer.knx_id,
        manufacturer_name=manufacturer.name,
        devices_imported=imported_devices_resp
    )


def _process_single_knxprod(file_bytes: bytes, filename: str, db: Session) -> UploadResponse:
    try:
        resp = _save_knxprod_db(file_bytes, filename, db)
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
            resp = _save_knxprod_db(fbytes, fname, db)
            savepoint.commit()
            success_count += 1
            results.append(BatchItemResult(
                filename=resp.filename,
                status="success",
                message="Erfolgreich importiert",
                file_size_bytes=resp.file_size_bytes,
                sha256=resp.sha256,
                manufacturer_id=resp.manufacturer_id,
                manufacturer_name=resp.manufacturer_name,
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

