from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Device, KnxprodFile, Manufacturer
from app.schemas.download import DownloadRequest

router = APIRouter(tags=["Download (.yaml)"])


def _serve_device_yaml(device: Device, db: Session) -> Response:
    """
    Delivers the KoNfiX-YAML specification for a device.
    Zero dependency on legacy .knxprod binary files: if yaml_content is missing,
    it is synthesized on the fly from the database records and saved.
    """
    if device.yaml_content:
        yaml_text = device.yaml_content
    else:
        from app.services.yaml_converter import build_konfix_yaml, generate_manufacturer_code
        mfg = device.manufacturer
        mfg_name = mfg.name if mfg else "Unbekannter Hersteller"
        mfg_code = (mfg.code if mfg else None) or generate_manufacturer_code(mfg_name, mfg.knx_id if mfg else None)
        if mfg and not mfg.code:
            mfg.code = mfg_code

        app0 = device.applications[0] if device.applications else None
        yaml_text = build_konfix_yaml(
            manufacturer_code=mfg_code,
            manufacturer_name=mfg_name,
            legacy_knx_id=mfg.knx_id if mfg else None,
            order_number=device.order_number,
            device_name=device.name,
            description=device.description,
            hardware_name=device.hardware_name,
            hardware_version=device.hardware_version,
            bus_current_ma=device.bus_current_ma,
            application_id=app0.app_id if app0 else None,
            application_name=app0.name if app0 else None,
            application_version=app0.version if app0 else None,
            mask_version=app0.mask_version if app0 else None,
            source_url=device.knxprod_file.source_url if device.knxprod_file else None,
        )
        device.yaml_content = yaml_text
        try:
            db.commit()
        except Exception:
            db.rollback()

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
        "Sendet einen JSON-Request mit Filterkriterien (z. B. `order_number`, `device_id`, "
        "oder `sha256`) und erhält die passende KoNfiX-YAML-Gerätedefinition als text/yaml zurück."
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
        file_rec = db.query(KnxprodFile).filter(KnxprodFile.sha256.ilike(req.sha256.strip())).first()
        if file_rec:
            device = db.query(Device).filter(Device.knxprod_file_id == file_rec.id).first()
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Keine Gerätedefinition mit SHA256 '{req.sha256}' gefunden."
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bitte mindestens 'order_number', 'device_id' oder 'sha256' im JSON-Body angeben."
        )

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Kein Gerät für die Anfrage gefunden."
        )

    return _serve_device_yaml(device, db)


from fastapi.responses import RedirectResponse, Response
from app.config import settings

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

    if (redirect or settings.PREFER_SOURCE_REDIRECT) and device.knxprod_file and device.knxprod_file.source_url:
        return RedirectResponse(url=device.knxprod_file.source_url, status_code=status.HTTP_302_FOUND)

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

    if (redirect or settings.PREFER_SOURCE_REDIRECT) and device.knxprod_file and device.knxprod_file.source_url:
        return RedirectResponse(url=device.knxprod_file.source_url, status_code=status.HTTP_302_FOUND)

    return _serve_device_yaml(device, db)
