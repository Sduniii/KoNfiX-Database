from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Device, Manufacturer
from app.schemas.download import DownloadRequest
from app.services.yaml_converter import device_to_konfix_yaml

router = APIRouter(tags=["Download (.yaml)"])


def _serve_device_yaml(device: Device, db: Session) -> Response:
    """
    Delivers the KoNfiX-YAML specification for a device, synthesized on the fly
    directly from the relational database records.
    """
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


@router.post(
    "/download",
    response_class=Response,
    summary="Download KoNfiX-YAML device definition via POST",
    description=(
        "Sendet einen JSON-Request mit Filterkriterien (z. B. `order_number`, `device_id`) "
        "und erhält die passende KoNfiX-YAML-Gerätedefinition als text/yaml zurück."
    ),
    responses={
        200: {
            "description": "Die KoNfiX-YAML-Gerätedefinition als text/yaml."
        },
        404: {
            "description": "Kein passendes Gerät gefunden."
        }
    }
)
def download_yaml_post(
    req: DownloadRequest,
    db: Session = Depends(get_db)
):
    """Downloads a KoNfiX-YAML device definition matching the criteria provided in the POST body."""
    device = None

    if req.device_id:
        device = db.query(Device).filter(Device.id == req.device_id).first()
    elif req.order_number:
        if req.exact_match:
            device = db.query(Device).filter(Device.order_number.ilike(req.order_number.strip())).first()
        else:
            device = db.query(Device).filter(Device.order_number.ilike(f"%{req.order_number.strip()}%")).first()
    elif req.sha256:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suche per KNXPROD-SHA256 wird nicht mehr unterstützt. Bitte 'order_number' oder 'device_id' verwenden."
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bitte mindestens 'order_number' oder 'device_id' im JSON-Body angeben."
        )

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kein Gerät für die Anfrage gefunden."
        )

    return _serve_device_yaml(device, db)


@router.get(
    "/download",
    response_class=Response,
    summary="Download KoNfiX-YAML device definition by query parameter",
    description="Download per HTTP GET anhand von ?order_number=..."
)
def download_yaml_get_query(
    order_number: str = Query(..., description="Bestellnummer des Geräts"),
    redirect: bool = Query(False, description="Falls vorhanden, direkt zur offiziellen Hersteller-URL per HTTP 302 weiterleiten"),
    db: Session = Depends(get_db)
):
    device = db.query(Device).filter(
        Device.order_number.ilike(order_number.strip())
    ).first()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Keine Datei für Bestellnummer '{order_number}' gefunden."
        )

    if (redirect or settings.PREFER_SOURCE_REDIRECT) and device.source_url:
        return RedirectResponse(url=device.source_url, status_code=status.HTTP_302_FOUND)

    return _serve_device_yaml(device, db)


@router.get(
    "/download/{order_number:path}",
    response_class=Response,
    summary="Download KoNfiX-YAML device definition (.yaml) via GET",
    description="Download per HTTP GET anhand der Bestellnummer. Liefert ausschließlich KoNfiX-YAML aus."
)
def download_yaml_get(
    order_number: str,
    redirect: bool = Query(False, description="Falls vorhanden, direkt zur offiziellen Hersteller-URL per HTTP 302 weiterleiten"),
    db: Session = Depends(get_db)
):
    device = db.query(Device).filter(
        Device.order_number.ilike(order_number.strip())
    ).first()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Keine Datei für Bestellnummer '{order_number}' gefunden."
        )

    if (redirect or settings.PREFER_SOURCE_REDIRECT) and device.source_url:
        return RedirectResponse(url=device.source_url, status_code=status.HTTP_302_FOUND)

    return _serve_device_yaml(device, db)
