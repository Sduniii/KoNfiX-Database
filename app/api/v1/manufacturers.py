from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any

from app.database import get_db
from app.models import Manufacturer, Device, KnxprodFile
from app.schemas.manufacturer import ManufacturerResponse

router = APIRouter(tags=["Manufacturers & Statistics"])

@router.get(
    "/manufacturers",
    response_model=List[ManufacturerResponse],
    summary="List all KNX manufacturers",
    description="Liefert alle registrierten KNX-Hersteller inklusive der Anzahl ihrer katalogisierten Geräte."
)
def list_manufacturers(db: Session = Depends(get_db)):
    results = (
        db.query(Manufacturer, func.count(Device.id).label("device_count"))
        .outerjoin(Device, Device.manufacturer_id == Manufacturer.id)
        .group_by(Manufacturer.id)
        .order_by(Manufacturer.name.asc())
        .all()
    )

    manufacturers_out = []
    for mfg, count in results:
        manufacturers_out.append(ManufacturerResponse(
            id=mfg.id,
            knx_id=mfg.knx_id,
            name=mfg.name,
            country=mfg.country,
            website=mfg.website,
            logo_url=mfg.logo_url,
            created_at=mfg.created_at,
            device_count=count
        ))

    return manufacturers_out

@router.get(
    "/stats",
    summary="Catalog statistics",
    description="Statistische Kennzahlen über den aktuellen Gerätekatalog."
)
def get_stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    devices_count = db.query(func.count(Device.id)).scalar() or 0
    mfg_count = db.query(func.count(Manufacturer.id)).scalar() or 0
    files_count = db.query(func.count(KnxprodFile.id)).scalar() or 0
    total_size = db.query(func.sum(KnxprodFile.file_size_bytes)).scalar() or 0

    return {
        "devices_total": devices_count,
        "manufacturers_total": mfg_count,
        "files_total": files_count,
        "total_catalog_size_bytes": total_size,
        "total_catalog_size_mb": round(total_size / (1024 * 1024), 2)
    }
