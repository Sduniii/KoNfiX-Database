from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import create_engine, func, text
from sqlalchemy.orm import sessionmaker

from app.api.v1.auth import is_admin_authenticated
from app.api.v1.manufacturers import invalidate_catalog_caches
from app.config import BASE_DIR, Settings, settings
import app.database as db_module
from app.database import Base, ensure_database_ready
from app.models import (
    ApplicationProgram,
    AssignRule,
    CommunicationObject,
    Device,
    Manufacturer,
    Parameter,
    Translation,
)
from scripts.migrate_sqlite_to_sql import (
    import_yaml_directory_to_target,
    migrate_sqlite_to_target,
)

router = APIRouter(tags=["Admin Migration"])

ENV_FILE_PATH: Path = BASE_DIR / ".env"
SOURCE_SQLITE_PATH: Path = BASE_DIR / "data" / "konfix_database.db"


def _mask_db_url(url: str) -> str:
    if not url:
        return ""
    return re.sub(r"://([^:/@]+):([^@]+)@", r"://\1:***@", url)


def _read_env_migration_flag(env_path: Path) -> Optional[bool]:
    if not env_path.exists():
        return None
    try:
        content = env_path.read_text(encoding="utf-8")
    except Exception:
        return None
    result: Optional[bool] = None
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" in stripped:
            key, val = stripped.split("=", 1)
            if key.strip() == "ENABLE_DB_MIGRATION":
                clean_val = val.strip().strip("\"'").lower()
                result = clean_val in ("true", "1", "yes", "on")
    return result


def _sync_settings_from_env_if_needed(env_path: Optional[Path] = None) -> None:
    """
    Falls auf Plesk die .env im laufenden Betrieb geändert wurde (ohne Passenger-Neustart),
    werden DATABASE_URL und ENABLE_DB_MIGRATION dynamisch nachgeladen.
    """
    target_env = env_path or ENV_FILE_PATH
    if not target_env.exists():
        return
    try:
        content = target_env.read_text(encoding="utf-8")
        defined_keys = {
            line.strip().split("=", 1)[0].strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#") and "=" in line
        }
        fresh = Settings(_env_file=target_env)
        if "ENABLE_DB_MIGRATION" in defined_keys:
            settings.ENABLE_DB_MIGRATION = fresh.ENABLE_DB_MIGRATION
        if ("DATABASE_URL" in defined_keys or "DB_HOST" in defined_keys) and (
            fresh.DATABASE_URL != settings.DATABASE_URL
        ):
            settings.DATABASE_URL = fresh.DATABASE_URL
            db_module.engine = db_module._build_engine(settings.DATABASE_URL)
            db_module.SessionLocal.configure(bind=db_module.engine)
            db_module._DB_INITIALIZED = False
    except Exception:
        pass


def is_migration_enabled(env_path: Optional[Path] = None) -> bool:
    target_env = env_path or ENV_FILE_PATH
    file_flag = _read_env_migration_flag(target_env)
    if file_flag is not None:
        settings.ENABLE_DB_MIGRATION = file_flag
        return file_flag
    return bool(settings.ENABLE_DB_MIGRATION)


def disable_migration_flag_in_env(env_path: Optional[Path] = None) -> Path:
    """
    Setzt ENABLE_DB_MIGRATION=false in der .env-Datei sowie sofort im Speicher.
    """
    settings.ENABLE_DB_MIGRATION = False
    target_env = env_path or ENV_FILE_PATH

    if target_env.exists():
        try:
            lines = target_env.read_text(encoding="utf-8").splitlines()
        except Exception:
            lines = []
    else:
        lines = []

    updated = False
    new_lines: List[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key == "ENABLE_DB_MIGRATION":
                if not updated:
                    new_lines.append("ENABLE_DB_MIGRATION=false")
                    updated = True
                continue
        new_lines.append(line)

    if not updated:
        if new_lines and new_lines[-1].strip() != "":
            new_lines.append("")
        new_lines.append("# Automatisch nach abgeschlossener Web-Migration gesperrt:")
        new_lines.append("ENABLE_DB_MIGRATION=false")

    target_env.parent.mkdir(parents=True, exist_ok=True)
    target_env.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return target_env


def _generate_connection_hint(error_msg: Optional[str]) -> Optional[str]:
    if not error_msg:
        return None
    err_lower = error_msg.lower()
    if "1045" in error_msg or "access denied" in err_lower:
        match = re.search(r"for user '([^']+)'@'([^']+)'", error_msg)
        user_info = f" für Benutzer '{match.group(1)}' von Host '{match.group(2)}'" if match else ""
        return (
            f"MySQL-Zugriff verweigert{user_info}. "
            "Netcup/Plesk-Lösung: Im Plesk-Panel unter 'Datenbanken' -> 'Benutzerverwaltung' "
            "beim Datenbank-Benutzer die Zugriffskontrolle von 'Nur lokale Verbindungen' auf "
            "'Verbindungen von beliebigen Hosts zulassen (%)' umstellen oder in der .env "
            "DB_HOST=127.0.0.1 bzw. DB_HOST=localhost sowie das Passwort prüfen."
        )
    if "can't connect" in err_lower or "connection refused" in err_lower:
        return (
            "Verbindung zum Datenbank-Server fehlgeschlagen. "
            "Bitte DB_HOST und DB_PORT in der .env überprüfen (z. B. 127.0.0.1 oder Hostname laut Plesk)."
        )
    if "unknown database" in err_lower or "1049" in error_msg:
        return (
            "Die angegebene Datenbank existiert nicht. Bitte im Plesk-Panel unter 'Datenbanken' "
            "prüfen, ob der Datenbankname (DB_NAME) exakt übereinstimmt."
        )
    return None


def _inspect_db_counts(db_url: str) -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "connected": False,
        "error": None,
        "hint": None,
        "manufacturers_count": 0,
        "devices_count": 0,
        "com_objects_count": 0,
        "parameters_count": 0,
        "translations_count": 0,
    }
    try:
        eng = db_module._build_engine(db_url)
        Base.metadata.create_all(bind=eng)
        SessionMaker = sessionmaker(autocommit=False, autoflush=False, bind=eng)
        with SessionMaker() as session:
            info["manufacturers_count"] = session.query(func.count(Manufacturer.id)).scalar() or 0
            info["devices_count"] = session.query(func.count(Device.id)).scalar() or 0
            info["com_objects_count"] = session.query(func.count(CommunicationObject.id)).scalar() or 0
            info["parameters_count"] = session.query(func.count(Parameter.id)).scalar() or 0
            info["translations_count"] = session.query(func.count(Translation.id)).scalar() or 0
            info["connected"] = True
        eng.dispose()
    except Exception as exc:
        info["error"] = str(exc)
        info["hint"] = _generate_connection_hint(str(exc))
    return info


class MigrationRunRequest(BaseModel):
    migrate_from_sqlite: bool = True
    sync_relational_and_counts: bool = True
    import_yaml_files: bool = False
    vacuum_sqlite: bool = True
    disable_flag_after_success: bool = True
    admin_key: Optional[str] = None


@router.get(
    "/admin/migration-status",
    summary="Get database migration status (requires ENABLE_DB_MIGRATION=true)",
)
def get_migration_status():
    _sync_settings_from_env_if_needed()
    if not is_migration_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Die Datenbank-Migration ist deaktiviert (ENABLE_DB_MIGRATION=false in .env).",
        )

    sqlite_exists = SOURCE_SQLITE_PATH.exists() and SOURCE_SQLITE_PATH.stat().st_size > 0
    sqlite_size_mb = (
        round(SOURCE_SQLITE_PATH.stat().st_size / (1024 * 1024), 2)
        if sqlite_exists
        else 0.0
    )
    sqlite_counts = (
        _inspect_db_counts(f"sqlite:///{SOURCE_SQLITE_PATH.resolve()}")
        if sqlite_exists
        else {
            "connected": False,
            "manufacturers_count": 0,
            "devices_count": 0,
            "com_objects_count": 0,
            "parameters_count": 0,
            "translations_count": 0,
        }
    )

    target_url = settings.DATABASE_URL
    source_url = f"sqlite:///{SOURCE_SQLITE_PATH.resolve()}" if sqlite_exists else ""
    is_external_sql = not target_url.startswith("sqlite:")
    is_separate_target = bool(sqlite_exists and target_url != source_url)

    target_counts = _inspect_db_counts(target_url)

    storage_dir = Path(settings.STORAGE_DIR)
    yaml_files = (
        list(storage_dir.glob("*.yaml")) + list(storage_dir.glob("*.yml"))
        if storage_dir.exists()
        else []
    )

    return {
        "migration_enabled": True,
        "admin_key_required": bool((settings.ADMIN_KEY or settings.API_KEY).strip()),
        "source_sqlite": {
            "path": str(SOURCE_SQLITE_PATH),
            "exists": sqlite_exists,
            "size_mb": sqlite_size_mb,
            **sqlite_counts,
        },
        "yaml_files_count": len(yaml_files),
        "target_db": {
            "engine": target_url.split("://", 1)[0] if "://" in target_url else "sqlite",
            "masked_url": _mask_db_url(target_url),
            "is_external_sql": is_external_sql,
            "is_separate_target": is_separate_target,
            **target_counts,
        },
        "fallback_active": db_module.is_db_fallback_active(),
        "last_db_error": db_module.get_last_db_error(),
    }


@router.post(
    "/admin/migrate",
    summary="Execute one-time database migration & lock .env flag",
)
def run_database_migration(
    payload: MigrationRunRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None),
    api_key: Optional[str] = Query(None),
):
    _sync_settings_from_env_if_needed()
    if not is_migration_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Die Datenbank-Migration ist deaktiviert (ENABLE_DB_MIGRATION=false in .env).",
        )

    from app.api.v1.auth import get_configured_admin_key

    if get_configured_admin_key():
        effective_key = payload.admin_key or x_api_key or api_key
        if not is_admin_authenticated(
            x_api_key=effective_key,
            authorization=authorization,
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Ungültiger oder fehlender ADMIN_KEY.",
            )

    t0 = time.perf_counter()
    logs: List[str] = []

    target_url = settings.DATABASE_URL
    sqlite_exists = SOURCE_SQLITE_PATH.exists() and SOURCE_SQLITE_PATH.stat().st_size > 0
    source_url = f"sqlite:///{SOURCE_SQLITE_PATH.resolve()}" if sqlite_exists else ""

    # Vorab-Prüfung: Ist die Ziel-Datenbank erreichbar?
    target_check = _inspect_db_counts(target_url)
    if not target_check["connected"]:
        err_hint = f" {target_check['hint']}" if target_check.get("hint") else ""
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ziel-Datenbank ({_mask_db_url(target_url)}) nicht erreichbar: {target_check['error']}.{err_hint}",
        )

    try:
        # 1. Ziel-Schema initialisieren & Spalten prüfen
        logs.append(f"Initialisiere Ziel-Datenbank ({_mask_db_url(target_url)})...")
        tgt_eng = db_module._build_engine(target_url)
        db_module._setup_schema_and_columns(tgt_eng)
        logs.append("✓ Tabellen-Schema und Zählspalten (inkl. MEDIUMTEXT für MySQL/MariaDB) bereit.")

        # 2. Daten aus lokaler SQLite-Datenbank in Ziel-DB migrieren (wenn unterschiedlich)
        if payload.migrate_from_sqlite and sqlite_exists and target_url != source_url:
            logs.append(f"Starte Daten-Migration von {SOURCE_SQLITE_PATH.name} -> Ziel-Datenbank...")
            migrate_sqlite_to_target(source_sqlite=SOURCE_SQLITE_PATH, target_url=target_url)
            logs.append("✓ Alle Hersteller, Geräte, KOs, Parameter, Zuweisungen und Übersetzungen aus SQLite übertragen.")
        elif payload.migrate_from_sqlite and target_url == source_url:
            logs.append("ℹ️ Quell- und Ziel-Datenbank sind identisch (SQLite) – überspringe Kopiervorgang.")

        # Re-bind aktive Engine und SessionLocal an die Ziel-Datenbank
        db_module.engine = tgt_eng
        db_module.SessionLocal.configure(bind=tgt_eng)
        db_module._FALLBACK_ACTIVE = False
        db_module._LAST_DB_ERROR = None
        db_module._DB_INITIALIZED = True

        # 3. Optional: YAML-Dateien aus catalog_files/ importieren
        if payload.import_yaml_files:
            yaml_dir = Path(settings.STORAGE_DIR)
            if yaml_dir.exists():
                logs.append(f"Prüfe YAML-Dateien in {yaml_dir}...")
                import_yaml_directory_to_target(yaml_dir=yaml_dir, target_url=target_url)
                logs.append("✓ YAML-Verzeichnis-Abgleich abgeschlossen.")

        # 4. Relationale Tabellen & Count-Spalten synchronisieren
        if payload.sync_relational_and_counts:
            logs.append("Synchronisiere relationale Tabellen und denormalisierte Zählspalten...")
            db_module._migrate_devices_to_relational()
            logs.append("✓ Zählspalten (com_objects_count, parameters_count, translations_count) synchronisiert.")

        # 5. Optional: SQLite VACUUM & ANALYZE
        if payload.vacuum_sqlite and sqlite_exists:
            before_mb = SOURCE_SQLITE_PATH.stat().st_size / (1024 * 1024)
            sq_eng = create_engine(source_url, connect_args={"check_same_thread": False})
            with sq_eng.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                conn.execute(text("VACUUM"))
                conn.execute(text("ANALYZE"))
            sq_eng.dispose()
            after_mb = SOURCE_SQLITE_PATH.stat().st_size / (1024 * 1024)
            logs.append(f"✓ SQLite VACUUM & ANALYZE ausgeführt ({before_mb:.2f} MB -> {after_mb:.2f} MB).")

        invalidate_catalog_caches()

        # 6. Flag in .env auf false setzen
        env_flag_disabled = False
        if payload.disable_flag_after_success:
            env_file = disable_migration_flag_in_env()
            env_flag_disabled = True
            logs.append(f"🔒 ENABLE_DB_MIGRATION=false wurde in '{env_file.name}' gespeichert. Die Migrationsseite ist ab sofort gesperrt.")

        final_counts = _inspect_db_counts(target_url)
        duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        logs.append(f"✅ Migration erfolgreich abgeschlossen in {duration_ms} ms.")

        return {
            "status": "success",
            "duration_ms": duration_ms,
            "env_flag_disabled": env_flag_disabled,
            "logs": logs,
            "target_db": {
                "masked_url": _mask_db_url(target_url),
                **final_counts,
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fehler während der Migration: {exc}",
        )
