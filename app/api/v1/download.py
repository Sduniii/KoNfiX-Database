from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy.orm import Session
from pathlib import Path

from app.config import settings
from app.database import get_db
from app.models import Device, KnxprodFile, Manufacturer
from app.schemas.download import DownloadRequest
from app.services.storage import storage_service

router = APIRouter(tags=["Download (.yaml / .knxprod)"])


@router.post(
    "/download",
    response_class=FileResponse,
    summary="Download device definition via POST",
    description=(
        "Sendet einen JSON-Request mit Filterkriterien (z. B. `order_number`, `device_id`, "
        "oder `sha256`) und erhält die passende Datei zurück."
    ),
    responses={
        200: {
            "description": "Die Gerätedatei als Stream."
        },
        404: {
            "description": "Kein passendes Gerät oder keine Datei gefunden."
        }
    }
)
def download_knxprod_post(
    req: DownloadRequest,
    db: Session = Depends(get_db)
):
    """Downloads a device definition file matching the criteria provided in the POST body."""
    query = db.query(Device).join(Device.knxprod_file)

    if req.device_id:
        device = query.filter(Device.id == req.device_id).first()
    elif req.order_number:
        if req.exact_match:
            device = query.filter(Device.order_number.ilike(req.order_number.strip())).first()
        else:
            device = query.filter(Device.order_number.ilike(f"%{req.order_number.strip()}%")).first()
    elif req.sha256:
        file_rec = db.query(KnxprodFile).filter(KnxprodFile.sha256.ilike(req.sha256.strip())).first()
        if not file_rec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Keine Datei mit SHA256 '{req.sha256}' gefunden."
            )
        return _serve_file(file_rec, "unknown")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bitte mindestens 'order_number', 'device_id' oder 'sha256' im JSON-Body angeben."
        )

    if not device or not device.knxprod_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Kein Gerät oder keine zugehörige Datei für die Anfrage gefunden."
        )

    return _serve_file(device.knxprod_file, device.order_number, device=device)


@router.get(
    "/download/{order_number}",
    summary="Download device definition (.yaml / .knxprod) via GET",
    description=(
        "Klassischer Download per HTTP GET anhand der Bestellnummer. "
        "Mit Parameter ?redirect=true wird bei hinterlegter Hersteller-URL direkt per HTTP 302 weitergeleitet. "
        "Mit Parameter ?format=yaml wird die KoNfiX-YAML-Definition ausgeliefert."
    )
)
def download_knxprod_get(
    order_number: str,
    redirect: bool = Query(False, description="Falls vorhanden, direkt zur offiziellen Hersteller-Download-URL per HTTP 302 weiterleiten"),
    format: Optional[str] = Query(None, description="Format ('yaml' oder 'raw')"),
    db: Session = Depends(get_db)
):
    device = db.query(Device).join(Device.knxprod_file).filter(
        Device.order_number.ilike(order_number.strip())
    ).first()

    if not device or not device.knxprod_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Keine Datei für Bestellnummer '{order_number}' gefunden."
        )

    force_yaml = (format == "yaml")
    return _serve_file(device.knxprod_file, device.order_number, prefer_redirect=redirect, device=device, force_yaml=force_yaml)


@router.get(
    "/knxprod/{file_id}/download",
    summary="Download file by ID",
    include_in_schema=False
)
def download_by_file_id(file_id: int, db: Session = Depends(get_db)):
    file_rec = db.query(KnxprodFile).filter(KnxprodFile.id == file_id).first()
    if not file_rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Datei nicht gefunden")
    return _serve_file(file_rec, f"file_{file_id}")


def _serve_file(
    file_rec: KnxprodFile,
    order_number: str,
    prefer_redirect: bool = False,
    device: Optional[Device] = None,
    force_yaml: bool = False
) -> Response:
    if force_yaml and device and device.yaml_content:
        return Response(
            content=device.yaml_content,
            media_type="text/yaml; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{device.order_number}.yaml"',
                "X-KoNfiX-Order-Number": device.order_number,
                "Access-Control-Expose-Headers": "Content-Disposition, X-KoNfiX-Order-Number"
            }
        )

    should_redirect = prefer_redirect or settings.PREFER_SOURCE_REDIRECT
    if should_redirect and file_rec.source_url:
        return RedirectResponse(url=file_rec.source_url, status_code=status.HTTP_302_FOUND)

    if not file_rec.storage_path:
        if file_rec.source_url:
            return RedirectResponse(url=file_rec.source_url, status_code=status.HTTP_302_FOUND)
        if device and device.yaml_content:
            return Response(
                content=device.yaml_content,
                media_type="text/yaml; charset=utf-8",
                headers={
                    "Content-Disposition": f'attachment; filename="{device.order_number}.yaml"',
                    "X-KoNfiX-Order-Number": device.order_number,
                    "Access-Control-Expose-Headers": "Content-Disposition, X-KoNfiX-Order-Number"
                }
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Die physische Datei wurde auf dem Server nicht gefunden."
        )

    try:
        file_path = storage_service.get_file_path(file_rec.storage_path)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Zugriff verweigert: Ungültiger Dateipfad."
        )

    if not file_path.exists():
        if file_rec.source_url:
            return RedirectResponse(url=file_rec.source_url, status_code=status.HTTP_302_FOUND)
        if device and device.yaml_content:
            return Response(
                content=device.yaml_content,
                media_type="text/yaml; charset=utf-8",
                headers={
                    "Content-Disposition": f'attachment; filename="{device.order_number}.yaml"',
                    "X-KoNfiX-Order-Number": device.order_number,
                    "Access-Control-Expose-Headers": "Content-Disposition, X-KoNfiX-Order-Number"
                }
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Die physische Datei wurde auf dem Server nicht gefunden."
        )

    filename = file_rec.filename
    is_yaml = filename.lower().endswith((".yaml", ".yml")) or file_rec.mime_type == "text/yaml"

    if is_yaml:
        media_type = "text/yaml; charset=utf-8"
        if not filename.lower().endswith((".yaml", ".yml")):
            filename += ".yaml"
    else:
        media_type = "application/octet-stream"
        if not filename.lower().endswith(".knxprod"):
            filename += ".knxprod"

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-KNX-Order-Number": order_number,
        "X-KoNfiX-Order-Number": order_number,
        "X-Checksum-SHA256": file_rec.sha256,
        "Access-Control-Expose-Headers": "Content-Disposition, X-KNX-Order-Number, X-KoNfiX-Order-Number, X-Checksum-SHA256"
    }

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=filename,
        headers=headers
    )
