from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy.orm import Session
from pathlib import Path

from app.config import settings
from app.database import get_db
from app.models import Device, KnxprodFile, Manufacturer
from app.schemas.download import DownloadRequest
from app.services.storage import storage_service

router = APIRouter(tags=["Download (.knxprod)"])


@router.post(
    "/download",
    response_class=FileResponse,
    summary="Download .knxprod via POST (application/octet-stream)",
    description=(
        "Sendet einen JSON-Request mit Filterkriterien (z. B. `order_number`, `device_id`, "
        "oder `sha256`) und erhält die passende .knxprod-Binärdatei als `application/octet-stream` zurück."
    ),
    responses={
        200: {
            "content": {"application/octet-stream": {}},
            "description": "Die rohe .knxprod-Binärdatei als Stream."
        },
        404: {
            "description": "Kein passendes Gerät oder keine KNX-Datei gefunden."
        }
    }
)
def download_knxprod_post(
    req: DownloadRequest,
    db: Session = Depends(get_db)
):
    """Downloads a .knxprod file matching the criteria provided in the POST body."""
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
            detail=f"Kein Gerät oder keine zugehörige .knxprod-Datei für die Anfrage gefunden."
        )

    return _serve_file(device.knxprod_file, device.order_number)


@router.get(
    "/download/{order_number}",
    summary="Download .knxprod via GET (application/octet-stream)",
    description=(
        "Klassischer Download per HTTP GET anhand der Bestellnummer. "
        "Mit Parameter ?redirect=true wird bei hinterlegter Hersteller-URL direkt per HTTP 302 weitergeleitet."
    )
)
def download_knxprod_get(
    order_number: str,
    redirect: bool = Query(False, description="Falls vorhanden, direkt zur offiziellen Hersteller-Download-URL per HTTP 302 weiterleiten"),
    db: Session = Depends(get_db)
):
    device = db.query(Device).join(Device.knxprod_file).filter(
        Device.order_number.ilike(order_number.strip())
    ).first()

    if not device or not device.knxprod_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Keine .knxprod-Datei für Bestellnummer '{order_number}' gefunden."
        )

    return _serve_file(device.knxprod_file, device.order_number, prefer_redirect=redirect)


@router.get(
    "/knxprod/{file_id}/download",
    summary="Download .knxprod by file ID",
    include_in_schema=False
)
def download_by_file_id(file_id: int, db: Session = Depends(get_db)):
    file_rec = db.query(KnxprodFile).filter(KnxprodFile.id == file_id).first()
    if not file_rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Datei nicht gefunden")
    return _serve_file(file_rec, f"file_{file_id}")


def _serve_file(file_rec: KnxprodFile, order_number: str, prefer_redirect: bool = False) -> Response:
    should_redirect = prefer_redirect or settings.PREFER_SOURCE_REDIRECT
    if should_redirect and file_rec.source_url:
        return RedirectResponse(url=file_rec.source_url, status_code=status.HTTP_302_FOUND)

    try:
        file_path = storage_service.get_file_path(file_rec.storage_path)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Zugriff verweigert: Ungültiger Dateipfad."
        )

    if not file_path.exists():
        # Fallback to source_url if file was not stored locally (e.g. metadata-only catalog mode)
        if file_rec.source_url:
            return RedirectResponse(url=file_rec.source_url, status_code=status.HTTP_302_FOUND)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Die physische .knxprod-Datei wurde auf dem Server nicht gefunden."
        )

    # Use original or sanitized filename
    filename = file_rec.filename
    if not filename.lower().endswith(".knxprod"):
        filename += ".knxprod"

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-KNX-Order-Number": order_number,
        "X-Checksum-SHA256": file_rec.sha256,
        "Access-Control-Expose-Headers": "Content-Disposition, X-KNX-Order-Number, X-Checksum-SHA256"
    }

    return FileResponse(
        path=str(file_path),
        media_type="application/octet-stream",
        filename=filename,
        headers=headers
    )
