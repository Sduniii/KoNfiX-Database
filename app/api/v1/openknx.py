import io
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status, Response
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.models.knx_gateway import KnxGateway
from app.schemas.openknx import (
    OpenKnxRepositorySchema,
    OpenKnxDeviceSchema,
    KnxGatewayCreate,
    KnxGatewayResponse,
    ImportReleaseRequest,
    DeviceRestartRequest,
    FileListRequest,
    FileDeleteRequest,
    DirCreateRequest,
    FlashFirmwareRequest,
    FileItemSchema
)
from app.services.openknx import (
    release_service,
    task_runner,
    mdns_scanner,
    KnxGatewayDiscovery,
    KnxConnection,
    FileTransferClient,
    firmware_flasher,
    knxprod_generator
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/openknx", tags=["OpenKNX Toolbox Extra"])


def _get_gateway_conn(db: Session, gateway_id: Optional[int] = None) -> KnxConnection:
    if gateway_id:
        gw = db.query(KnxGateway).filter(KnxGateway.id == gateway_id).first()
        if not gw:
            raise HTTPException(status_code=404, detail="KNX Gateway nicht gefunden")
        return KnxConnection(host=gw.host, port=gw.port, protocol=gw.protocol)

    default_gw = db.query(KnxGateway).filter(KnxGateway.is_default == True).first()
    if default_gw:
        return KnxConnection(host=default_gw.host, port=default_gw.port, protocol=default_gw.protocol)

    first_gw = db.query(KnxGateway).first()
    if first_gw:
        return KnxConnection(host=first_gw.host, port=first_gw.port, protocol=first_gw.protocol)

    # Fallback to config default
    return KnxConnection(host=settings.KNX_DEFAULT_GATEWAY_IP, port=settings.KNX_DEFAULT_GATEWAY_PORT)


# ==============================================================================
# 1. Firmware & Releases Hub
# ==============================================================================
@router.get("/applications", summary="Listet alle OpenKNX-Module und Repositorien")
async def get_applications(force_refresh: bool = False):
    return await release_service.get_applications(force_refresh=force_refresh)


@router.get("/releases", summary="Listet alle OpenKNX-Releases und Assets")
async def get_releases(
    repository: Optional[str] = Query(None, description="Nach Repository filtern"),
    channel: Optional[str] = Query(None, description="'release' für stabile Versionen, 'dev' für Beta/Dev"),
    force_refresh: bool = False
):
    all_releases = await release_service.get_releases(force_refresh=force_refresh)
    if not repository:
        return all_releases

    repo_data = all_releases.get(repository)
    if not repo_data:
        raise HTTPException(status_code=404, detail=f"Repository '{repository}' nicht gefunden")

    if channel:
        is_dev = channel.lower() in ("dev", "beta")
        filtered_rels = [
            r for r in repo_data.get("releases", [])
            if (r.get("prerelease") if is_dev else not r.get("prerelease"))
        ]
        return {**repo_data, "releases": filtered_rels}

    return repo_data


@router.post("/releases/sync", summary="Synchronisiert OpenKNX-Releases von go.openknx.de")
async def sync_releases():
    await release_service.get_applications(force_refresh=True)
    releases = await release_service.get_releases(force_refresh=True)
    return {"status": "success", "repositories_count": len(releases)}


@router.post("/releases/import", summary="1-Klick-Import eines OpenKNX-Releases in den Katalog")
async def import_release(req: ImportReleaseRequest, db: Session = Depends(get_db)):
    """
    Lädt das OpenKNX-Release herunter, extrahiert die XML-Definition,
    speichert Hardware, KO-Objekte und Parameter in die Katalog-Datenbank
    und erzeugt die standardisierte .yaml sowie .knxprod Datei.
    """
    try:
        result = await release_service.import_release_to_catalog(req.repository, req.tag, db)
        return result
    except Exception as ex:
        logger.exception("Fehler beim Importieren des OpenKNX-Releases: %s", ex)
        raise HTTPException(status_code=422, detail=f"Import fehlgeschlagen: {ex}")


@router.get("/releases/download-asset", summary="Lädt ein Release-Asset herunter")
async def download_release_asset(
    repository: str,
    tag: str,
    asset_name: str
):
    releases_dict = await release_service.get_releases()
    repo_data = releases_dict.get(repository)
    if not repo_data:
        raise HTTPException(status_code=404, detail="Repository nicht gefunden")

    asset_url = None
    for r in repo_data.get("releases", []):
        if r.get("tag_name") == tag:
            for a in r.get("assets", []):
                if a.get("name") == asset_name:
                    asset_url = a.get("browser_download_url")
                    break
    if not asset_url:
        raise HTTPException(status_code=404, detail=f"Asset '{asset_name}' nicht im Release '{tag}' gefunden")

    local_path = release_service.downloads_dir / repository / tag / asset_name
    await release_service.download_asset(asset_url, local_path)
    return FileResponse(
        str(local_path),
        filename=asset_name,
        media_type="application/octet-stream"
    )


# ==============================================================================
# 2. Device Manager (mDNS & Bus Discovery)
# ==============================================================================
@router.get("/devices", summary="Gibt alle erkannten OpenKNX-Geräte mit Update-Status zurück")
async def get_devices():
    return mdns_scanner.get_cached_devices()


@router.post("/devices/scan-mdns", summary="Startet einen mDNS-Scan nach OpenKNX-Geräten (_openknx._tcp)")
async def scan_devices_mdns(timeout: float = Query(2.5, ge=1.0, le=10.0)):
    devices = await mdns_scanner.scan(timeout=timeout)
    return {"status": "success", "found_count": len(devices), "devices": devices}


@router.post("/devices/restart", summary="Sendet einen Neustart-Befehl an ein Gerät")
async def restart_device(req: DeviceRestartRequest, db: Session = Depends(get_db)):
    if req.target_address:
        conn = _get_gateway_conn(db, req.gateway_id)
        try:
            await conn.connect()
            await conn.restart_device(req.target_address)
            await conn.disconnect()
            return {"status": "success", "message": f"Neustart-Befehl an {req.target_address} gesendet."}
        except Exception as ex:
            raise HTTPException(status_code=500, detail=f"Bus-Neustart fehlgeschlagen: {ex}")
    raise HTTPException(status_code=400, detail="Keine Zieladresse angegeben")


# ==============================================================================
# 3. KNXnet/IP Gateway Connections
# ==============================================================================
@router.get("/gateways", response_model=List[KnxGatewayResponse], summary="Listet gespeicherte KNX-Gateways")
def list_gateways(db: Session = Depends(get_db)):
    gws = db.query(KnxGateway).all()
    return [
        KnxGatewayResponse(
            id=g.id,
            name=g.name,
            host=g.host,
            port=g.port,
            protocol=g.protocol,
            individual_address=g.individual_address,
            is_default=g.is_default,
            created_at=g.created_at.isoformat()
        )
        for g in gws
    ]


@router.post("/gateways", response_model=KnxGatewayResponse, summary="Erstellt ein neues KNX-Gateway Profil")
def create_gateway(req: KnxGatewayCreate, db: Session = Depends(get_db)):
    if req.is_default:
        db.query(KnxGateway).update({"is_default": False})
    gw = KnxGateway(
        name=req.name,
        host=req.host,
        port=req.port,
        protocol=req.protocol,
        individual_address=req.individual_address,
        is_default=req.is_default
    )
    db.add(gw)
    db.commit()
    db.refresh(gw)
    return KnxGatewayResponse(
        id=gw.id,
        name=gw.name,
        host=gw.host,
        port=gw.port,
        protocol=gw.protocol,
        individual_address=gw.individual_address,
        is_default=gw.is_default,
        created_at=gw.created_at.isoformat()
    )


@router.delete("/gateways/{gw_id}", summary="Löscht ein KNX-Gateway Profil")
def delete_gateway(gw_id: int, db: Session = Depends(get_db)):
    gw = db.query(KnxGateway).filter(KnxGateway.id == gw_id).first()
    if not gw:
        raise HTTPException(status_code=404, detail="Gateway nicht gefunden")
    db.delete(gw)
    db.commit()
    return {"status": "success", "message": "Gateway gelöscht"}


@router.post("/gateways/discover", summary="Sucht KNX IP Gateways im lokalen Netzwerk (Multicast)")
async def discover_gateways(timeout: float = Query(2.0, ge=1.0, le=5.0)):
    gateways = await KnxGatewayDiscovery.discover(timeout=timeout)
    return {"status": "success", "found_count": len(gateways), "gateways": gateways}


# ==============================================================================
# 4. KNX File Manager (Object 159 / FTM)
# ==============================================================================
@router.post("/file-manager/list", summary="Listet Dateien auf dem Speicher eines OpenKNX-Geräts")
async def list_device_files(req: FileListRequest, db: Session = Depends(get_db)):
    conn = _get_gateway_conn(db, req.gateway_id)
    try:
        await conn.connect()
        await conn.connect_individual(req.target_address)
        client = FileTransferClient(conn, req.target_address)
        items = await client.list_dir(req.remote_path)
        await conn.disconnect_individual(req.target_address)
        await conn.disconnect()
        return [
            {"name": i.name, "is_file": i.is_file, "path": i.path, "size": i.size}
            for i in items
        ]
    except Exception as ex:
        logger.exception("Fehler beim DirList: %s", ex)
        raise HTTPException(status_code=500, detail=f"Dateiabfrage fehlgeschlagen: {ex}")


@router.post("/file-manager/upload", summary="Überträgt eine Datei auf das OpenKNX-Gerät")
async def upload_device_file(
    target_address: str = Form(...),
    remote_path: str = Form(...),
    gateway_id: Optional[int] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    content = await file.read()
    conn = _get_gateway_conn(db, gateway_id)
    try:
        await conn.connect()
        await conn.connect_individual(target_address)
        client = FileTransferClient(conn, target_address)
        await client.upload_file(remote_path, content)
        await conn.disconnect_individual(target_address)
        await conn.disconnect()
        return {"status": "success", "message": f"Datei '{remote_path}' erfolgreich hochgeladen"}
    except Exception as ex:
        logger.exception("Fehler beim FileUpload: %s", ex)
        raise HTTPException(status_code=500, detail=f"Upload fehlgeschlagen: {ex}")


@router.get("/file-manager/download", summary="Lädt eine Datei vom OpenKNX-Gerät herunter")
async def download_device_file(
    target_address: str,
    remote_path: str,
    gateway_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    conn = _get_gateway_conn(db, gateway_id)
    try:
        await conn.connect()
        await conn.connect_individual(target_address)
        client = FileTransferClient(conn, target_address)
        data = await client.download_file(remote_path)
        await conn.disconnect_individual(target_address)
        await conn.disconnect()
        filename = remote_path.split("/")[-1] or "download.bin"
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as ex:
        logger.exception("Fehler beim FileDownload: %s", ex)
        raise HTTPException(status_code=500, detail=f"Download fehlgeschlagen: {ex}")


@router.post("/file-manager/delete", summary="Löscht eine Datei auf dem OpenKNX-Gerät")
async def delete_device_file(req: FileDeleteRequest, db: Session = Depends(get_db)):
    conn = _get_gateway_conn(db, req.gateway_id)
    try:
        await conn.connect()
        await conn.connect_individual(req.target_address)
        client = FileTransferClient(conn, req.target_address)
        success = await client.delete_file(req.remote_path)
        await conn.disconnect_individual(req.target_address)
        await conn.disconnect()
        if not success:
            raise HTTPException(status_code=400, detail="Datei konnte nicht gelöscht werden")
        return {"status": "success", "message": f"Datei '{req.remote_path}' gelöscht"}
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Löschen fehlgeschlagen: {ex}")


@router.post("/file-manager/mkdir", summary="Erstellt ein Verzeichnis auf dem Gerät")
async def create_device_dir(req: DirCreateRequest, db: Session = Depends(get_db)):
    conn = _get_gateway_conn(db, req.gateway_id)
    try:
        await conn.connect()
        await conn.connect_individual(req.target_address)
        client = FileTransferClient(conn, req.target_address)
        success = await client.create_dir(req.remote_path)
        await conn.disconnect_individual(req.target_address)
        await conn.disconnect()
        if not success:
            raise HTTPException(status_code=400, detail="Verzeichnis konnte nicht erstellt werden")
        return {"status": "success", "message": f"Ordner '{req.remote_path}' erstellt"}
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Ordnererstellung fehlgeschlagen: {ex}")


@router.post("/file-manager/format", summary="Formatiert das Flash-Dateisystem des Geräts")
async def format_device_filesystem(req: FileDeleteRequest, db: Session = Depends(get_db)):
    conn = _get_gateway_conn(db, req.gateway_id)
    try:
        await conn.connect()
        await conn.connect_individual(req.target_address)
        client = FileTransferClient(conn, req.target_address)
        success = await client.format_filesystem()
        await conn.disconnect_individual(req.target_address)
        await conn.disconnect()
        if not success:
            raise HTTPException(status_code=400, detail="Dateisystem konnte nicht formatiert werden")
        return {"status": "success", "message": "Dateisystem erfolgreich formatiert"}
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Formatieren fehlgeschlagen: {ex}")


# ==============================================================================
# 5. Firmware Flasher & OTA
# ==============================================================================
@router.post("/flash", summary="Startet einen asynchronen Firmware-Flash-Vorgang (OTA oder KNX-Bus)")
async def flash_firmware(req: FlashFirmwareRequest, db: Session = Depends(get_db)):
    """
    Flasht Firmware auf ein Gerät im Hintergrund:
    - method 'ota': IP + Port erforderlich
    - method 'bus': target_address (KNX-PA) + gateway erforderlich
    """
    firmware_bytes: Optional[bytes] = None

    # Load from OpenKNX Release asset if specified
    if req.repository and req.tag and req.asset_name:
        releases_dict = await release_service.get_releases()
        repo_data = releases_dict.get(req.repository)
        if not repo_data:
            raise HTTPException(status_code=404, detail="Repository nicht gefunden")
        asset_url = None
        for r in repo_data.get("releases", []):
            if r.get("tag_name") == req.tag:
                for a in r.get("assets", []):
                    if a.get("name") == req.asset_name:
                        asset_url = a.get("browser_download_url")
                        break
        if not asset_url:
            raise HTTPException(status_code=404, detail="Firmware-Asset nicht im Release gefunden")

        local_path = release_service.downloads_dir / req.repository / req.tag / req.asset_name
        await release_service.download_asset(asset_url, local_path)
        with open(local_path, "rb") as f:
            firmware_bytes = f.read()

    if not firmware_bytes:
        raise HTTPException(status_code=400, detail="Keine Firmware-Daten angegeben")

    gw_conn = _get_gateway_conn(db, req.gateway_id) if req.method == "bus" else None

    async def _flash_task(task_obj):
        def _prog(pct, msg):
            task_obj.progress = pct
            task_obj.message = msg
            task_obj.logs.append(f"[{pct}%] {msg}")

        if req.method == "bus":
            if not req.target_address:
                raise ValueError("Für Bus-Flash wird eine physikalische KNX-Adresse benötigt")
            await gw_conn.connect()
            await gw_conn.connect_individual(req.target_address)
            await firmware_flasher.flash_via_bus(
                gw_conn, req.target_address, firmware_bytes, progress_cb=_prog
            )
            await gw_conn.disconnect_individual(req.target_address)
            await gw_conn.disconnect()
        elif req.method == "ota":
            if not req.ip or not req.port:
                raise ValueError("Für OTA-Flash wird IP und Port benötigt")
            await firmware_flasher.flash_via_network_ota(
                req.ip, req.port, firmware_bytes, progress_cb=_prog
            )
        else:
            raise ValueError(f"Unbekannte Flash-Methode: {req.method}")

    task = task_runner.create_task(
        name=f"Flash {req.asset_name or 'Firmware'} via {req.method.upper()}",
        task_type="firmware_flash",
        target_coro=_flash_task
    )
    return {"status": "started", "task_id": task.task_id}


# ==============================================================================
# 6. Tasks & Action Runner
# ==============================================================================
@router.get("/tasks", summary="Listet alle Hintergrund-Tasks der Toolbox")
def get_tasks():
    return task_runner.list_tasks()


@router.get("/tasks/{task_id}", summary="Liefert Status und Fortschritt eines Tasks")
def get_task_status(task_id: str):
    task = task_runner.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task nicht gefunden")
    return task.to_dict()


@router.post("/tasks/{task_id}/cancel", summary="Bricht einen laufenden Task ab")
def cancel_task(task_id: str):
    success = task_runner.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="Task konnte nicht abgebrochen werden")
    return {"status": "success", "message": "Task abgebrochen"}


# ==============================================================================
# 7. .knxprod Generator & Exporter
# ==============================================================================
@router.post("/knxprod/generate", summary="Generiert ein .knxprod-Archiv aus einer OpenKNX-XML")
async def generate_knxprod(
    xml_file: UploadFile = File(...),
    manufacturer_id: str = Form("M-00FA")
):
    xml_bytes = await xml_file.read()
    knxprod_data = await knxprod_generator.generate_knxprod_bytes(
        xml_bytes=xml_bytes,
        manufacturer_id=manufacturer_id
    )
    base_name = xml_file.filename.rsplit(".", 1)[0] if xml_file.filename else "OpenKNX"
    return Response(
        content=knxprod_data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{base_name}.knxprod"'}
    )
