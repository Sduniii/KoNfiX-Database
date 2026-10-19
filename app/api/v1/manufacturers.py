import time
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CommunicationObject, Device, Manufacturer, Parameter
from app.schemas.manufacturer import ManufacturerResponse

router = APIRouter(tags=["Manufacturers & Statistics"])

_CACHE_TTL_SECONDS = 30.0
_mfg_cache: Optional[Tuple[float, Tuple[int, int, int], List[ManufacturerResponse]]] = None
_stats_cache: Optional[Tuple[float, Tuple[int, int, int], Dict[str, Any]]] = None


def invalidate_catalog_caches() -> None:
    """Invalidates in-memory caches for /manufacturers and /stats after catalog mutations."""
    global _mfg_cache, _stats_cache
    _mfg_cache = None
    _stats_cache = None


def _get_cache_signature(db: Session) -> Tuple[int, int, int]:
    bind_id = id(db.get_bind())
    devices_count = db.query(func.count(Device.id)).scalar() or 0
    mfg_count = db.query(func.count(Manufacturer.id)).scalar() or 0
    return (bind_id, int(devices_count), int(mfg_count))


@router.get(
    "/manufacturers",
    response_model=List[ManufacturerResponse],
    summary="List all KNX manufacturers",
    description="Liefert alle registrierten KNX-Hersteller inklusive der Anzahl ihrer katalogisierten Geräte."
)
def list_manufacturers(db: Session = Depends(get_db)):
    global _mfg_cache
    now = time.monotonic()
    sig = _get_cache_signature(db)
    if _mfg_cache is not None and (now - _mfg_cache[0]) < _CACHE_TTL_SECONDS and _mfg_cache[1] == sig:
        return _mfg_cache[2]

    results = (
        db.query(Manufacturer, func.count(Device.id).label("device_count"))
        .outerjoin(Device, Device.manufacturer_id == Manufacturer.id)
        .group_by(Manufacturer.id)
        .order_by(Manufacturer.name.asc())
        .all()
    )

    manufacturers_out = [
        ManufacturerResponse(
            id=mfg.id,
            knx_id=mfg.knx_id or mfg.code or "",
            name=mfg.name,
            country=mfg.country,
            website=mfg.website,
            logo_url=mfg.logo_url,
            created_at=mfg.created_at,
            device_count=count,
        )
        for mfg, count in results
    ]

    _mfg_cache = (now, sig, manufacturers_out)
    return manufacturers_out


@router.get(
    "/stats",
    summary="Catalog statistics",
    description="Statistische Kennzahlen über den aktuellen Gerätekatalog."
)
def get_stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    global _stats_cache
    now = time.monotonic()
    sig = _get_cache_signature(db)
    if _stats_cache is not None and (now - _stats_cache[0]) < _CACHE_TTL_SECONDS and _stats_cache[1] == sig:
        return _stats_cache[2]

    _, devices_count, mfg_count = sig
    cos_count = db.query(func.count(CommunicationObject.id)).scalar() or 0
    params_count = db.query(func.count(Parameter.id)).scalar() or 0
    total_bytes = int(db.query(func.coalesce(func.sum(func.length(Device.yaml_content)), 0)).scalar() or 0)

    stats = {
        "devices_total": devices_count,
        "manufacturers_total": mfg_count,
        "communication_objects_total": int(cos_count),
        "parameters_total": int(params_count),
        "files_total": devices_count,
        "total_catalog_size_bytes": total_bytes,
        "total_catalog_size_mb": round(total_bytes / (1024 * 1024), 2),
    }
    _stats_cache = (now, sig, stats)
    return stats

