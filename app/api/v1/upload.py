import os

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
from app.schemas.upload import ImportedApplication, ImportedDevice, UploadResponse
from app.services.knxprod_parser import parse_knxprod_bytes
from app.services.storage import storage_service

DB_GET_DEPENDENCY = Depends(get_db)
FILE_OPEN = File(..., description="Die .knxprod-Datei als Binärdatei (Multipart-Formularfeld 'file')")

router = APIRouter(tags=["Upload (.knxprod)"])

def verify_api_key(x_api_key: str | None = Header(None)):
    if settings.API_KEY and x_api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungültiger oder fehlender X-API-Key"
        )
    return True

@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload .knxprod file (raw application/octet-stream or multipart)",
    description=(
        "Ultra-einfacher Upload für Hersteller: Sende die rohe .knxprod-Datei direkt als "
        "`application/octet-stream` im Body (optional mit Header `X-File-Name: ...`). "
        "Das Backend entpackt das ZIP, parst die KNX-XML-Struktur (M-xxxx.xml) automatisch "
        "und registriert Hersteller, Geräte, Applikationen und Metadaten in der Datenbank."
    )
)
async def upload_knxprod(
    request: Request,
    db: Session = DB_GET_DEPENDENCY,
    x_file_name: str | None = Header(None, description="Optionaler Dateiname der .knxprod-Datei"),
    filename: str | None = Query(None, description="Optionaler Dateiname via Query-Parameter"),
    _authorized: bool = Depends(verify_api_key)
):
    content_type = request.headers.get("content-type", "").lower()
    file_bytes: bytes = b""
    resolved_filename = x_file_name or filename or "device.knxprod"

    if "application/octet-stream" in content_type or not content_type:
        # Raw binary streaming body
        file_bytes = await request.body()
    elif "multipart/form-data" in content_type:
        form = await request.form()
        upload_field = form.get("file")
        if upload_field and hasattr(upload_field, "read"):
            file_bytes = await upload_field.read()
            if hasattr(upload_field, "filename") and upload_field.filename:
                resolved_filename = upload_field.filename
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formular enthält kein gültiges 'file' Feld"
            )
    else:
        # Fallback: attempt to read raw body anyway
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formular enthält kein gültiges 'file' Feld"
        )

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Keine Dateidaten empfangen. Bitte sende die Binärdaten der .knxprod-Datei."
        )

    return _process_and_save_knxprod(file_bytes, resolved_filename, db)


@router.post(
    "/upload/form",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload .knxprod via standard Form Multipart",
    include_in_schema=False
)
async def upload_knxprod_form(
    file: UploadFile = FILE_OPEN,  
    db: Session = DB_GET_DEPENDENCY,
    _authorized: bool = Depends(verify_api_key)
):
    content = await file.read()
    return _process_and_save_knxprod(content, file.filename or "device.knxprod", db)


def _process_and_save_knxprod(file_bytes: bytes, filename: str, db: Session) -> UploadResponse:
    # 1. Parse XML and validate ZIP structure
    try:
        parsed = parse_knxprod_bytes(file_bytes)
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Fehler bei der KNXProd-Verarbeitung: {e!s}"
        )

    # 2. Store binary file
    stored_path, sha256_hash, file_size = storage_service.save_knxprod_bytes(file_bytes, filename)

    # 3. Check or create KnxprodFile record
    knx_file_rec = db.query(KnxprodFile).filter(KnxprodFile.sha256 == sha256_hash).first()
    if not knx_file_rec:
        knx_file_rec = KnxprodFile(
            filename=os.path.basename(filename),
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

    db.commit()

    return UploadResponse(
        status="success",
        message="KNXProd-Datei erfolgreich empfangen, geparst und indexiert",
        filename=os.path.basename(filename),
        file_size_bytes=file_size,
        sha256=sha256_hash,
        manufacturer_id=manufacturer.knx_id,
        manufacturer_name=manufacturer.name,
        devices_imported=imported_devices_resp
    )
