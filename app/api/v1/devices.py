# isort: skip_file
from typing import Annotated, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.v1.auth import verify_admin_key, verify_api_key
from app.database import get_db
from app.models import Device, Manufacturer, CommunicationObject, Parameter
from app.schemas.device import (
    ApplicationProgramResponse,
    BatchDeleteRequest,
    BatchDeleteResponse,
    DeviceListResponse,
    DeviceResponse,
    DeviceUpdateRequest,
    KnxprodFileInfo,
    ManufacturerSummary,
    CommunicationObjectResponse,
    ParameterResponse,
)


router = APIRouter(tags=["Devices & Catalog"])
DB_SESSION_DEPENDENCY = Depends(get_db)


def _to_device_response(d: Device) -> DeviceResponse:
    file_info = None
    if d.source_url:
        file_info = KnxprodFileInfo(
            source_url=d.source_url,
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
        source_url=d.source_url,
        manufacturer=ManufacturerSummary(
            id=d.manufacturer.id,
            code=d.manufacturer.code,
            knx_id=d.manufacturer.knx_id,
            name=d.manufacturer.name
        ),
        knxprod_file=file_info,
        applications=apps,
        yaml_url=f"/api/v1/devices/{d.order_number}/yaml",
        com_objects_count=len(d.communication_objects) if d.communication_objects else 0,
        parameters_count=len(d.parameters) if d.parameters else 0,
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
    manufacturer_id: str | None = Query(None, description="Filter nach Hersteller-ID (Zahl, Code oder KNX-ID wie 'M-0083')"),
    manufacturer_code: str | None = Query(None, description="Filter nach Hersteller-Code (z.B. 'mdt', 'openknx')"),
    page: int = Query(1, ge=1, description="Seitennummer"),
    page_size: int = Query(20, ge=1, le=100, description="Einträge pro Seite"),
    db: Session = DB_SESSION_DEPENDENCY,
):
    query = db.query(Device).join(Manufacturer)

    if manufacturer_id:
        mid_str = manufacturer_id.strip()
        if mid_str.isdigit():
            query = query.filter(or_(Device.manufacturer_id == int(mid_str), Manufacturer.knx_id.ilike(mid_str)))
        else:
            query = query.filter(or_(Manufacturer.knx_id.ilike(mid_str), Manufacturer.code.ilike(mid_str)))

    if manufacturer_code:
        query = query.filter(Manufacturer.code.ilike(manufacturer_code.strip()))

    if q:
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Device.name.ilike(term),
                Device.order_number.ilike(term),
                Device.description.ilike(term),
                Manufacturer.name.ilike(term),
                Manufacturer.code.ilike(term)
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


def _serve_yaml_for_device(device: Device, db: Session) -> Response:
    from app.services.yaml_converter import device_to_konfix_yaml
    yaml_text = device_to_konfix_yaml(device)

    return Response(
        content=yaml_text,
        media_type="text/yaml; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{device.order_number}.yaml"',
            "X-KoNfiX-Order-Number": device.order_number,
            "Access-Control-Expose-Headers": "Content-Disposition, X-KoNfiX-Order-Number"
        }
    )


@router.get(
    "/devices/yaml",
    summary="Get full KoNfiX-YAML definition by query parameter",
    description="Liefert die vollständige KoNfiX-YAML-Gerätedefinition anhand von ?order_number=..."
)
def get_device_yaml_query(
    order_number: str = Query(..., description="Bestellnummer des Geräts"),
    db: Session = DB_SESSION_DEPENDENCY
):
    device = db.query(Device).filter(Device.order_number.ilike(order_number.strip())).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Gerät mit Bestellnummer '{order_number}' wurde nicht gefunden."
        )
    return _serve_yaml_for_device(device, db)


@router.get(
    "/devices/{order_number:path}/yaml",
    summary="Get full KoNfiX-YAML definition for device",
    description="Liefert die vollständige, offene KoNfiX-YAML-Gerätedefinition inklusive aller Kommunikationsobjekte und Parameter on-the-fly."
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
    return _serve_yaml_for_device(device, db)


@router.get(
    "/devices/{order_number:path}/communication-objects",
    response_model=List[CommunicationObjectResponse],
    summary="Get communication objects for device",
    description="Liefert alle Kommunikationsobjekte eines Geräts mit optionalem Filter nach DPT oder Funktion."
)
def get_device_communication_objects(
    order_number: str,
    dpt: Optional[str] = Query(None, description="Filter nach Datenpunkttyp (z. B. '1.001')"),
    q: Optional[str] = Query(None, description="Suche in Name oder Funktion"),
    db: Session = DB_SESSION_DEPENDENCY
):
    device = db.query(Device).filter(Device.order_number.ilike(order_number.strip())).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Gerät mit Bestellnummer '{order_number}' wurde nicht gefunden."
        )

    query = db.query(CommunicationObject).filter(CommunicationObject.device_id == device.id)
    if dpt:
        query = query.filter(CommunicationObject.dpt.ilike(f"%{dpt.strip()}%"))
    if q:
        term = f"%{q.strip()}%"
        query = query.filter(or_(CommunicationObject.name.ilike(term), CommunicationObject.function.ilike(term)))

    return query.order_by(CommunicationObject.number.asc()).all()


@router.get(
    "/devices/{order_number:path}/parameters",
    response_model=List[ParameterResponse],
    summary="Get parameters for device",
    description="Liefert alle Parameter eines Geräts mit optionalem Filter nach Seite oder Typ."
)
def get_device_parameters(
    order_number: str,
    page_name: Optional[str] = Query(None, description="Filter nach Seitenpfad"),
    param_type: Optional[str] = Query(None, description="Filter nach Typ (enum, number, text, float)"),
    q: Optional[str] = Query(None, description="Suche in Parameter-Name oder Text"),
    db: Session = DB_SESSION_DEPENDENCY
):
    device = db.query(Device).filter(Device.order_number.ilike(order_number.strip())).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Gerät mit Bestellnummer '{order_number}' wurde nicht gefunden."
        )

    query = db.query(Parameter).filter(Parameter.device_id == device.id)
    if page_name:
        query = query.filter(Parameter.page.ilike(f"%{page_name.strip()}%"))
    if param_type:
        query = query.filter(Parameter.type == param_type.strip())
    if q:
        term = f"%{q.strip()}%"
        query = query.filter(or_(Parameter.name.ilike(term), Parameter.text.ilike(term)))

    return query.order_by(Parameter.id.asc()).all()


@router.get(
    "/devices/{order_number:path}",
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
    "/devices/{order_number:path}",
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
        device.source_url = update_data.source_url.strip() if update_data.source_url else None

    db.commit()
    db.refresh(device)
    return _to_device_response(device)


@router.delete(
    "/devices/{order_number:path}",
    summary="Delete device from catalog (Admin / Takedown)",
    description="Entfernt ein Gerät und alle zugehörigen relationalen Daten aus dem Katalog."
)
def delete_device(
    order_number: str,
    db: Session = DB_SESSION_DEPENDENCY,
    _authorized: bool = Depends(verify_admin_key)
):
    device = db.query(Device).filter(Device.order_number.ilike(order_number.strip())).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Gerät mit Bestellnummer '{order_number}' wurde nicht gefunden."
        )

    db.delete(device)
    db.commit()
    return {
        "status": "success",
        "message": f"Gerät '{order_number}' wurde erfolgreich aus dem Katalog gelöscht."
    }


@router.post(
    "/devices/batch-delete",
    response_model=BatchDeleteResponse,
    summary="Delete multiple devices from catalog (Admin / Batch Takedown)",
    description="Entfernt mehrere Geräte gebündelt aus dem Katalog."
)
def batch_delete_devices(
    payload: BatchDeleteRequest,
    db: Session = DB_SESSION_DEPENDENCY,
    _authorized: bool = Depends(verify_admin_key)
):
    if not payload.order_numbers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Keine Bestellnummern zum Löschen angegeben."
        )

    deleted_order_numbers = []
    errors = []

    for raw_on in payload.order_numbers:
        on = raw_on.strip()
        if not on:
            continue
        device = db.query(Device).filter(Device.order_number.ilike(on)).first()
        if not device:
            errors.append(f"Gerät mit Bestellnummer '{on}' nicht gefunden.")
            continue

        db.delete(device)
        deleted_order_numbers.append(on)

    db.commit()

    return BatchDeleteResponse(
        deleted_count=len(deleted_order_numbers),
        deleted_order_numbers=deleted_order_numbers,
        errors=errors,
        message=f"{len(deleted_order_numbers)} Gerät(e) erfolgreich aus dem Katalog gelöscht."
    )
