import asyncio
import io
import json
import logging
import os
import re
import time
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import httpx
from sqlalchemy.orm import Session

from app.config import BASE_DIR, settings
from app.models import Manufacturer, Device, ApplicationProgram, CommunicationObject, Parameter, AssignRule, Translation
from app.services.knxprod_parser import parse_knxprod_bytes, ParsedKnxprod
from app.services.yaml_converter import generate_manufacturer_code
from app.services.storage import storage_service

logger = logging.getLogger(__name__)


def parse_semver_tuple(version_str: str) -> Tuple[int, int, int, str]:
    """Parses a version string like 'v1.10.0-Dev' or '3.5.2' into (major, minor, patch, prerelease)."""
    clean = version_str.strip()
    if clean.startswith("v") or clean.startswith("V"):
        clean = clean[1:]
    m = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:-([a-zA-Z0-9.]+))?", clean)
    if not m:
        return (0, 0, 0, clean)
    major = int(m.group(1) or 0)
    minor = int(m.group(2) or 0)
    patch = int(m.group(3) or 0)
    pre = m.group(4) or ""
    return (major, minor, patch, pre)


def compare_semver(v1: str, v2: str) -> int:
    """Returns 1 if v1 > v2, -1 if v1 < v2, 0 if equal."""
    t1 = parse_semver_tuple(v1)
    t2 = parse_semver_tuple(v2)
    # Compare (major, minor, patch)
    if t1[:3] > t2[:3]:
        return 1
    elif t1[:3] < t2[:3]:
        return -1
    # If numeric parts equal: no prerelease is newer than prerelease
    if not t1[3] and t2[3]:
        return 1
    elif t1[3] and not t2[3]:
        return -1
    return 0


class OpenKnxReleaseService:
    def __init__(self):
        self.cache_dir = settings.OPENKNX_CACHE_DIR
        self.downloads_dir = self.cache_dir / "downloads"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)

    async def get_applications(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        cache_file = self.cache_dir / "applications.json"
        if not force_refresh and cache_file.exists():
            age = time.time() - cache_file.stat().st_mtime
            if age < settings.OPENKNX_CACHE_TTL_SECONDS:
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as ex:
                    logger.warning("Fehler beim Lesen des Applikations-Caches: %s", ex)

        # Abruf von go.openknx.de
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(settings.OPENKNX_APPLICATIONS_URL)
                resp.raise_for_status()
                data = resp.json()
                repos = data.get("Repositories", [])
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(repos, f, ensure_ascii=False, indent=2)
                return repos
        except Exception as ex:
            logger.error("Fehler beim Abrufen von OpenKNX-Applikationen: %s", ex)
            if cache_file.exists():
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            return []

    async def get_releases(self, force_refresh: bool = False) -> Dict[str, Any]:
        cache_file = self.cache_dir / "releases.json"
        if not force_refresh and cache_file.exists():
            age = time.time() - cache_file.stat().st_mtime
            if age < settings.OPENKNX_CACHE_TTL_SECONDS:
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as ex:
                    logger.warning("Fehler beim Lesen des Release-Caches: %s", ex)

        # Abruf von go.openknx.de
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                resp = await client.get(settings.OPENKNX_RELEASES_URL)
                resp.raise_for_status()
                data = resp.json()
                releases_data = data.get("data", {})
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(releases_data, f, ensure_ascii=False, indent=2)
                return releases_data
        except Exception as ex:
            logger.error("Fehler beim Abrufen von OpenKNX-Releases: %s", ex)
            if cache_file.exists():
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            return {}

    async def get_app_mappings(self) -> Dict[str, Dict[str, Any]]:
        """Maps appId (e.g. '$A011') to repository info."""
        apps = await self.get_applications()
        mappings = {}
        for repo in apps:
            repo_name = repo.get("Repository")
            help_thread = repo.get("HelpThread")
            desc = repo.get("Description")
            for app in repo.get("Apps", []):
                app_id = app.get("AppId")
                label = app.get("Label")
                if app_id:
                    mappings[app_id.upper()] = {
                        "repository": repo_name,
                        "label": label,
                        "description": desc,
                        "help_thread": help_thread,
                    }
        return mappings

    async def get_latest_version_for_app(self, app_id: str) -> Optional[str]:
        mappings = await self.get_app_mappings()
        app_meta = mappings.get(app_id.upper())
        if not app_meta:
            return None
        repo_name = app_meta["repository"]
        releases_dict = await self.get_releases()
        repo_info = releases_dict.get(repo_name)
        if not repo_info:
            return None

        is_dev = (app_meta.get("label") or "").lower() in ("dev", "beta")
        latest_ver = None

        for rel in repo_info.get("releases", []):
            tag = rel.get("tag_name", "")
            prerelease = rel.get("prerelease", False)
            if is_dev or not prerelease:
                if latest_ver is None or compare_semver(tag, latest_ver) > 0:
                    latest_ver = tag
        return latest_ver

    async def download_asset(
        self,
        download_url: str,
        target_path: Path,
        progress_cb: Optional[Any] = None
    ) -> Path:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists() and target_path.stat().st_size > 0:
            return target_path

        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            async with client.stream("GET", download_url) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                downloaded = 0
                temp_file = target_path.with_suffix(".tmp")
                with open(temp_file, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_cb and total > 0:
                            percent = int((downloaded / total) * 100)
                            progress_cb(percent, downloaded, total)
                temp_file.replace(target_path)
        return target_path

    async def import_release_to_catalog(
        self,
        repo_name: str,
        tag_name: str,
        db: Session,
        progress_cb: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        1-Click Ingestion of an OpenKNX release:
        1. Downloads the release ZIP package.
        2. Inspects and extracts the ETS XML specification.
        3. Parses all devices, hardware, parameters, and communication objects.
        4. Saves the device into KoNfiX database (M-00FA OpenKNX).
        5. Saves standard YAML specification and packages `.knxprod` file.
        """
        releases_dict = await self.get_releases()
        repo_info = releases_dict.get(repo_name)
        if not repo_info:
            raise ValueError(f"OpenKNX Repository '{repo_name}' nicht gefunden.")

        target_release = None
        for rel in repo_info.get("releases", []):
            if rel.get("tag_name") == tag_name:
                target_release = rel
                break
        if not target_release:
            raise ValueError(f"Release '{tag_name}' für '{repo_name}' nicht gefunden.")

        assets = target_release.get("assets", [])
        if not assets:
            raise ValueError(f"Keine Assets im Release '{tag_name}' gefunden.")

        # Find main zip asset (usually Repo-Release-x.x.zip)
        zip_asset = None
        for a in assets:
            if a.get("name", "").endswith(".zip"):
                zip_asset = a
                break
        if not zip_asset:
            zip_asset = assets[0]

        asset_name = zip_asset["name"]
        asset_url = zip_asset["browser_download_url"]
        local_zip_path = self.downloads_dir / repo_name / tag_name / asset_name

        if progress_cb:
            progress_cb(10, "Lade Release-Archiv herunter...")

        await self.download_asset(asset_url, local_zip_path)

        if progress_cb:
            progress_cb(40, "Entpacke und analysiere OpenKNX-XML...")

        # Extract main XML and baggages from ZIP
        with open(local_zip_path, "rb") as f:
            zip_bytes = f.read()

        xml_content = None
        xml_filename = None
        baggages_dict: Dict[str, bytes] = {}

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for info in zf.infolist():
                fname = info.filename.replace("\\", "/")
                # Check for ETS XML (exclude content.xml)
                if fname.endswith(".xml") and not fname.endswith("content.xml"):
                    if xml_content is None or "data/" in fname:
                        xml_content = zf.read(info)
                        xml_filename = fname.split("/")[-1]
                # Collect baggage files
                if ".baggages/" in fname and not info.is_dir():
                    baggage_rel_path = fname.split(".baggages/", 1)[1]
                    baggages_dict[baggage_rel_path] = zf.read(info)

        if not xml_content:
            raise ValueError(f"Keine passende OpenKNX-Gerätedefinition (.xml) im Archiv '{asset_name}' gefunden.")

        if progress_cb:
            progress_cb(60, "Indexiere Hardware, Parameter und Kommunikationsobjekte...")

        # Wrap into a synthetic in-memory KNXprod zip with M-00FA.xml so standard parser handles it
        synthetic_buf = io.BytesIO()
        with zipfile.ZipFile(synthetic_buf, "w", zipfile.ZIP_DEFLATED) as szf:
            szf.writestr("M-00FA.xml", xml_content)
            for bg_path, bg_data in baggages_dict.items():
                szf.writestr(f"M-00FA/Baggages/{bg_path}", bg_data)

        # Parse using existing knxprod parser
        parsed_knx: ParsedKnxprod = parse_knxprod_bytes(synthetic_buf.getvalue())

        # Ensure OpenKNX Manufacturer exists
        mfg = db.query(Manufacturer).filter(Manufacturer.knx_id == "M-00FA").first()
        if not mfg:
            mfg = Manufacturer(
                knx_id="M-00FA",
                name="OpenKNX",
                code="openknx",
                country="DE"
            )
            db.add(mfg)
            db.flush()

        imported_devices = []
        catalog_dir = Path(settings.STORAGE_DIR) / "openknx"
        catalog_dir.mkdir(parents=True, exist_ok=True)

        # Save synthetic knxprod for downloads
        knxprod_filename = f"OpenKNX_{repo_name}_{tag_name}.knxprod".replace("/", "_")
        knxprod_path = catalog_dir / knxprod_filename
        with open(knxprod_path, "wb") as f:
            f.write(synthetic_buf.getvalue())

        for p_dev in parsed_knx.devices:
            # Check if device already exists
            existing_dev = db.query(Device).filter(
                Device.manufacturer_id == mfg.id,
                Device.order_number == p_dev.order_number
            ).first()

            if not existing_dev:
                dev = Device(
                    manufacturer_id=mfg.id,
                    order_number=p_dev.order_number,
                    name=p_dev.name,
                    description=p_dev.description or f"OpenKNX {repo_name} Release {tag_name}",
                    hardware_name=p_dev.hardware_name or repo_name,
                    hardware_version=p_dev.hardware_version or tag_name,
                    bus_current_ma=p_dev.bus_current_ma,
                    yaml_content=p_dev.yaml_content,
                    source_url=target_release.get("html_url")
                )
                db.add(dev)
                db.flush()
                target_dev = dev
            else:
                existing_dev.name = p_dev.name
                existing_dev.description = p_dev.description or f"OpenKNX {repo_name} Release {tag_name}"
                existing_dev.hardware_version = p_dev.hardware_version or tag_name
                existing_dev.yaml_content = p_dev.yaml_content
                existing_dev.source_url = target_release.get("html_url")
                db.flush()
                target_dev = existing_dev

            # Persist relational applications
            for app in p_dev.applications:
                db_app = db.query(ApplicationProgram).filter(
                    ApplicationProgram.device_id == target_dev.id,
                    ApplicationProgram.app_id == app.app_id
                ).first()
                if not db_app:
                    db_app = ApplicationProgram(
                        device_id=target_dev.id,
                        app_id=app.app_id,
                        name=app.name,
                        version=app.version,
                        mask_version=app.mask_version,
                        com_objects_count=app.com_objects_count,
                        parameters_count=app.parameters_count
                    )
                    db.add(db_app)
                    db.flush()

            # Save standalone YAML in catalog_files
            yaml_filename = f"OpenKNX_{p_dev.order_number}_{tag_name}.yaml".replace("/", "_")
            if p_dev.yaml_content:
                with open(catalog_dir / yaml_filename, "w", encoding="utf-8") as yf:
                    yf.write(p_dev.yaml_content)

            imported_devices.append({
                "order_number": p_dev.order_number,
                "name": p_dev.name,
                "hardware_version": p_dev.hardware_version,
                "apps_count": len(p_dev.applications)
            })

        db.commit()

        if progress_cb:
            progress_cb(100, f"{len(imported_devices)} OpenKNX-Geräte erfolgreich in den Katalog importiert!")

        return {
            "status": "success",
            "repository": repo_name,
            "tag": tag_name,
            "filename": knxprod_filename,
            "devices_imported": imported_devices
        }


release_service = OpenKnxReleaseService()
