# isort: skip_file
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Device, Manufacturer
from app.schemas.device import (
    ApplicationProgramResponse,
    DeviceListResponse,
    DeviceResponse,
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
            knx_id=d.manufacturer.knx_id,
            name=d.manufacturer.name
        ),
        knxprod_file=file_info,
        applications=apps,
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
