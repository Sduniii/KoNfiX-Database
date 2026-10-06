# isort: skip_file
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.v1.auth import verify_admin_key, verify_api_key
from app.database import get_db
from app.models import Device, KnxprodFile, Manufacturer
from app.schemas.device import (
    ApplicationProgramResponse,
    BatchDeleteRequest,
    BatchDeleteResponse,
    DeviceListResponse,
    DeviceResponse,
    DeviceUpdateRequest,
    KnxprodFileInfo,
    ManufacturerSummary,
)


router = APIRouter(tags=["Devices & Catalog"])
DB_SESSION_DEPENDENCY = Depends(get_db)

def _to_device_response(d: Device) -> DeviceResponse:
    file_info = None
    if d.knxprod_file:
        file_info = KnxprodFileInfo(
            id=d.knxprod_file.id,
            filename=d.knxprod_file.filename,
            file_size_bytes=d.knxprod_file.file_size_bytes,
            sha256=d.knxprod_file.sha256,
            source_url=d.knxprod_file.source_url,
            uploaded_at=d.knxprod_file.uploaded_at,
            download_url=f"/api/v1/download/{d.order_number}"
        )

    apps = [
        ApplicationProgramResponse(
            id=app.id,
            app_id=app.app_id,
            name=app.name,
            version=app.version,
            mask_version=app.mask_version,
            com_objects_count=app.com_objects_count,
            parameters_count=app.parameters_count
        )
        for app in d.applications
    ]

    return DeviceResponse(
        id=d.id,
        order_number=d.order_number,
        name=d.name,
        description=d.description,
        hardware_name=d.hardware_name,
        hardware_version=d.hardware_version,
        bus_current_ma=d.bus_current_ma,
        manufacturer=ManufacturerSummary(
            id=d.manufacturer.id,
            code=d.manufacturer.code,
            knx_id=d.manufacturer.knx_id,
            name=d.manufacturer.name
        ),
        knxprod_file=file_info,
        applications=apps,
        yaml_url=f"/api/v1/devices/{d.order_number}/yaml",
        created_at=d.created_at,
        updated_at=d.updated_at
    )

@router.get(
    "/devices",
    response_model=DeviceListResponse,
    summary="List and search KNX devices",
    description="Volltextsuche und Filterung nach Bestellnummer, Name, Beschreibung oder Hersteller."
)
def list_devices(
    q: str | None = Query(None, description="Suchbegriff (Bestellnummer, Gerätename, Beschreibung)"),
    manufacturer_id: str | None = Query(None, description="Filter nach KNX-Herstellerkennung (z.B. 'M-00C5')"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = DB_SESSION_DEPENDENCY
):
    query = db.query(Device).join(Device.manufacturer)

    if manufacturer_id:
        query = query.filter(Manufacturer.knx_id.ilike(manufacturer_id.strip()))

    if q:
        search = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Device.order_number.ilike(search),
                Device.name.ilike(search),
                Device.description.ilike(search),
                Manufacturer.name.ilike(search)
            )
        )

    total = query.count()
    devices = query.order_by(Device.name.asc()).offset((page - 1) * page_size).limit(page_size).all()

    return DeviceListResponse(
        total=total,
        page=page,
        page_size=page_size,
        devices=[_to_device_response(d) for d in devices]
    )

@router.get(
    "/devices/{order_number}",
    response_model=DeviceResponse,
    summary="Get single device details",
    description="Liefert alle technischen Details, Applikationsversionen und Download-URLs zu einem KNX-Gerät."
)
def get_device(order_number: str, db: Annotated[Session, Depends(get_db)]):
    device = db.query(Device).filter(Device.order_number.ilike(order_number.strip())).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Gerät mit Bestellnummer '{order_number}' wurde nicht gefunden."
        )
    return _to_device_response(device)


@router.patch(
    "/devices/{order_number}",
    response_model=DeviceResponse,
    summary="Update device metadata and manufacturer link (Admin)",
    description="Aktualisiert die Metadaten eines Geräts sowie die offizielle Hersteller-Quelle (source_url)."
)
def update_device(
    order_number: str,
    update_data: DeviceUpdateRequest,
    db: Session = DB_SESSION_DEPENDENCY,
    _authorized: bool = Depends(verify_admin_key)
):
    device = db.query(Device).filter(Device.order_number.ilike(order_number.strip())).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Gerät mit Bestellnummer '{order_number}' wurde nicht gefunden."
        )

    if update_data.name is not None:
        device.name = update_data.name.strip()
    if update_data.description is not None:
        device.description = update_data.description
    if update_data.hardware_name is not None:
        device.hardware_name = update_data.hardware_name
    if update_data.hardware_version is not None:
        device.hardware_version = update_data.hardware_version
    if update_data.bus_current_ma is not None:
        device.bus_current_ma = update_data.bus_current_ma

    if update_data.source_url is not None:
        clean_url = update_data.source_url.strip() if update_data.source_url else None
        if device.knxprod_file:
            device.knxprod_file.source_url = clean_url
        elif clean_url:
            # Create a placeholder KnxprodFile record for the link if none exists
            new_file = KnxprodFile(
                filename=f"{device.order_number}.knxprod",
                file_size_bytes=0,
                sha256=f"link_{device.order_number}",
                storage_path=None,
                source_url=clean_url,
                mime_type="application/octet-stream"
            )
            db.add(new_file)
            db.flush()
            device.knxprod_file_id = new_file.id

    db.commit()
    db.refresh(device)
    return _to_device_response(device)


@router.delete(
    "/devices/{order_number}",
    summary="Delete device from catalog (Admin / Takedown)",
    description="Entfernt ein Gerät und dessen Applikationen aus dem Katalog. Bei Bedarf wird die zugehörige Datei ebenfalls gelöscht."
)
def delete_device(
    order_number: str,
    delete_file: bool = Query(False, description="Zugehörige .knxprod-Datei ebenfalls vom Server löschen, falls keine anderen Geräte darauf verweisen"),
    db: Session = DB_SESSION_DEPENDENCY,
    _authorized: bool = Depends(verify_admin_key)
):
    import os
    device = db.query(Device).filter(Device.order_number.ilike(order_number.strip())).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Gerät mit Bestellnummer '{order_number}' wurde nicht gefunden."
        )

    file_rec = device.knxprod_file
    file_id = device.knxprod_file_id

    db.delete(device)
    db.flush()

    if file_rec and file_id:
        other_devices_count = db.query(Device).filter(Device.knxprod_file_id == file_id).count()
        if other_devices_count == 0 and delete_file:
            if file_rec.storage_path and os.path.exists(file_rec.storage_path):
                try:
                    os.remove(file_rec.storage_path)
                except OSError:
                    pass
            db.delete(file_rec)

    db.commit()
    return {
        "status": "success",
        "message": f"Gerät '{order_number}' wurde erfolgreich aus dem Katalog gelöscht."
    }


@router.post(
    "/devices/batch-delete",
    response_model=BatchDeleteResponse,
    summary="Delete multiple devices from catalog (Admin / Batch Takedown)",
    description="Entfernt mehrere Geräte und deren Applikationen gebündelt aus dem Katalog. Optional werden verwaiste Dateien vom Server gelöscht."
)
def batch_delete_devices(
    payload: BatchDeleteRequest,
    db: Session = DB_SESSION_DEPENDENCY,
    _authorized: bool = Depends(verify_admin_key)
):
    import os
    if not payload.order_numbers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Keine Bestellnummern zum Löschen angegeben."
        )

    deleted_order_numbers = []
    errors = []
    affected_file_ids = set()

    for raw_on in payload.order_numbers:
        on = raw_on.strip()
        if not on:
            continue
        device = db.query(Device).filter(Device.order_number.ilike(on)).first()
        if not device:
            errors.append(f"Gerät mit Bestellnummer '{on}' nicht gefunden.")
            continue

        if device.knxprod_file_id:
            affected_file_ids.add(device.knxprod_file_id)

        db.delete(device)
        deleted_order_numbers.append(on)

    db.flush()

    # Bereinigung der Dateien, falls gewünscht
    if payload.delete_files and affected_file_ids:
        for fid in affected_file_ids:
            remaining = db.query(Device).filter(Device.knxprod_file_id == fid).count()
            if remaining == 0:
                f_rec = db.query(KnxprodFile).filter(KnxprodFile.id == fid).first()
                if f_rec:
                    if f_rec.storage_path and os.path.exists(f_rec.storage_path):
                        try:
                            os.remove(f_rec.storage_path)
                        except OSError:
                            pass
                    db.delete(f_rec)

    db.commit()

    return BatchDeleteResponse(
        deleted_count=len(deleted_order_numbers),
        deleted_order_numbers=deleted_order_numbers,
        errors=errors,
        message=f"{len(deleted_order_numbers)} Gerät(e) erfolgreich aus dem Katalog gelöscht."
    )


@router.get(
    "/devices/{order_number}/yaml",
    summary="Get full KoNfiX-YAML definition for device",
    description="Liefert die vollständige, offene KoNfiX-YAML-Gerätedefinition inklusive aller Kommunikationsobjekte und Parameter."
)
def get_device_yaml(
    order_number: str,
    db: Session = DB_SESSION_DEPENDENCY
):
    device = db.query(Device).filter(Device.order_number.ilike(order_number.strip())).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Gerät mit Bestellnummer '{order_number}' wurde nicht gefunden."
        )

    if device.yaml_content:
        yaml_text = device.yaml_content
    else:
        # Generate on the fly if migrated without pre-stored yaml
        from app.services.yaml_converter import build_konfix_yaml, generate_manufacturer_code
        mfg_code = device.manufacturer.code or generate_manufacturer_code(device.manufacturer.name, device.manufacturer.knx_id)
        yaml_text = build_konfix_yaml(
            manufacturer_code=mfg_code,
            manufacturer_name=device.manufacturer.name,
            legacy_knx_id=device.manufacturer.knx_id,
            order_number=device.order_number,
            device_name=device.name,
            description=device.description,
            hardware_name=device.hardware_name,
            hardware_version=device.hardware_version,
            bus_current_ma=device.bus_current_ma,
            application_name=device.applications[0].name if device.applications else None,
            source_url=device.knxprod_file.source_url if device.knxprod_file else None,
        )

    return Response(
        content=yaml_text,
        media_type="text/yaml; charset=utf-8",
        headers={"Content-Disposition": f'inline; filename="{device.order_number}.yaml"'}
    )



