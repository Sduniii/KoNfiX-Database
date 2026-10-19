# Standard library
from contextlib import asynccontextmanager
from typing import Optional, Tuple

import anyio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import defer

from app.api.v1 import api_v1_router
from app.config import BASE_DIR, settings
from app.database import Base, ensure_database_ready

_INDEX_HTML_CACHE: Optional[Tuple[float, str]] = None


def init_db():
    try:
        # Ensure DB file and schema exist (with resilient SQLite fallback)
        ensure_database_ready()

        # Self-healing check for legacy manufacturer entries
        from app.database import SessionLocal
        from app.models import Manufacturer, Device

        db = SessionLocal()
        try:
            m_0083 = db.query(Manufacturer).filter(Manufacturer.knx_id == "M-0083").first()
            if m_0083 and "gira" in m_0083.name.lower():
                m_0083.name = "MDT technologies"
                # Ensure Gira exists as M-0008
                m_0008 = db.query(Manufacturer).filter(Manufacturer.knx_id == "M-0008").first()
                if not m_0008:
                    m_0008 = Manufacturer(knx_id="M-0008", name="GIRA Giersiepen")
                    db.add(m_0008)
                    db.flush()
                # Reassign any Gira demo devices (e.g. 216800) to M-0008
                gira_devices = (
                    db.query(Device)
                    .options(defer(Device.yaml_content))
                    .filter(Device.order_number == "216800")
                    .all()
                )
                for dev in gira_devices:
                    dev.manufacturer_id = m_0008.id
                db.commit()

            # Populate sample data only if explicitly enabled in configuration
            if settings.AUTO_SEED_DEMO_DATA and db.query(Device.id).first() is None:
                try:
                    from scripts.seed_sample_data import seed_database
                    seed_database()
                except Exception as seed_err:
                    print("Automatic seed skipped:", seed_err)
        except Exception as query_err:
            db.rollback()
            print(f"[KoNfiX DB] Warnung bei init_db Datenabgleich: {query_err}")
        finally:
            db.close()
    except Exception as fatal_err:
        print(f"[KoNfiX DB] Fehler in init_db (nicht-fatal, App startet weiter): {fatal_err}")


# Ensure DB schema exists on import (required for WSGI / Phusion Passenger)
init_db()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=f"""
{settings.APP_DESCRIPTION}

### Features
* **Zero-Config Upload für Hersteller**: `POST /api/v1/upload` mit `Content-Type: application/octet-stream` (automatische XML-Erkennung).
* **Download per POST**: `POST /api/v1/download` mit Filterkriterien gibt direkt die `.knxprod`-Datei als `application/octet-stream` zurück.
* **Klassischer Download per GET**: `GET /api/v1/download/{{order_number}}` (optional `?redirect=true` zur Hersteller-Original-URL).
* **Geräte- & Herstellersuche**: Volltextsuche und Filterung via `GET /api/v1/devices` und `GET /api/v1/manufacturers`.

### Rechtlicher Hinweis & Disclaimer (§ 23 MarkenG)
* **Unabhängiges Projekt**: KoNfiX ist ein unabhängiges Open-Source-Projekt und steht in keiner geschäftlichen Beziehung zur KNX Association cvba oder den gelisteten Herstellern.
* **Markenzeichen**: KNX® ist ein eingetragenes Warenzeichen der KNX Association cvba. Alle genannten Produkt- und Herstellernamen dienen ausschließlich der Identifikation und technischen Kompatibilitätsbeschreibung.
* **Notice-and-Takedown**: Rechteinhaber können Löschungsanfragen jederzeit an `{settings.LEGAL_CONTACT_EMAIL}` richten.
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",

    openapi_url="/openapi.json"
)

# GZip Compression Middleware for large YAML / JSON responses
app.add_middleware(GZipMiddleware, minimum_size=500)

# Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    if request.url.path in ("/docs", "/redoc"):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https://fastapi.tiangolo.com; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "object-src 'none'; "
            "base-uri 'self'"
        )
    else:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "object-src 'none'; "
            "base-uri 'self'"
        )
    if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=settings.cors_credentials_safe,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-KNX-Order-Number", "X-Checksum-SHA256"]
)

# Mount Static Files
static_dir = BASE_DIR / "app" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Include API Routers
app.include_router(api_v1_router)


@app.get("/health", tags=["System"], summary="Health check & active database status")
@app.get("/api/v1/system/status", tags=["System"], summary="System and active database status")
def health_status():
    from app.database import get_database_status_info
    db_info = get_database_status_info()
    return {
        "status": "healthy" if db_info["connected"] else "degraded",
        "app_name": settings.APP_NAME,
        "app_version": settings.APP_VERSION,
        "database": db_info,
    }


@app.get("/schema.json", include_in_schema=False)
@app.get("/schemas/konfix-device-v1.json", include_in_schema=False)
def serve_schema_direct(download: bool = False):
    from app.api.v1.schema import get_konfix_device_schema
    return get_konfix_device_schema(download=download)


@app.get("/template.yaml", include_in_schema=False)
@app.get("/schemas/konfix-template.yaml", include_in_schema=False)
@app.get("/schemas/template.yaml", include_in_schema=False)
def serve_template_direct():
    from app.api.v1.schema import get_konfix_template_yaml
    return get_konfix_template_yaml()



@app.get("/favicon.ico", include_in_schema=False)
@app.get("/favicon.svg", include_in_schema=False)
def serve_favicon():
    favicon_path = BASE_DIR / "app" / "static" / "favicon.svg"
    if favicon_path.exists():
        return FileResponse(
            str(favicon_path),
            media_type="image/svg+xml",
            headers={"Cache-Control": "public, max-age=86400"}
        )
    return Response(status_code=404)


# One-time Web Database Migration UI (only accessible when ENABLE_DB_MIGRATION=true in .env)
@app.get("/migrate", response_class=HTMLResponse, include_in_schema=False)
async def serve_migrate():
    from app.api.v1.migration import _sync_settings_from_env_if_needed, is_migration_enabled

    _sync_settings_from_env_if_needed()
    if not is_migration_enabled():
        locked_html = (
            "<!DOCTYPE html><html lang='de'><head><meta charset='UTF-8'>"
            "<title>Migration gesperrt</title>"
            "<style>body{background:#0b0f19;color:#f8fafc;font-family:system-ui,sans-serif;"
            "display:flex;align-items:center;justify-content:center;min-height:90vh;margin:0}"
            ".card{max-width:520px;background:#111827;border:1px solid rgba(255,255,255,0.1);"
            "border-radius:12px;padding:1.75rem;text-align:center}"
            "code{background:rgba(255,255,255,0.08);padding:0.15rem 0.4rem;border-radius:4px;color:#38bdf8}"
            "a{color:#38bdf8;text-decoration:none}</style></head><body>"
            "<div class='card'><h2>🔒 Datenbank-Migration deaktiviert</h2>"
            "<p style='color:#94a3b8;line-height:1.5'>Die einmalige Migrationsseite ist gesperrt "
            "(<code>ENABLE_DB_MIGRATION=false</code>). Um sie freizuschalten, setze in der "
            "<code>.env</code>-Datei temporär <code>ENABLE_DB_MIGRATION=true</code>.</p>"
            "<p style='margin-top:1.25rem'><a href='/'>← Zurück zum Katalog</a></p></div></body></html>"
        )
        return HTMLResponse(content=locked_html, status_code=403)

    migrate_template = BASE_DIR / "app" / "templates" / "migrate.html"
    if migrate_template.exists():
        async with await anyio.open_file(migrate_template, "r", encoding="utf-8") as f:
            html_content = await f.read()
        return HTMLResponse(
            content=html_content,
            headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
        )
    return HTMLResponse(content="<h1>Migration template missing</h1>", status_code=404)


# Root Web Frontend
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_index():
    global _INDEX_HTML_CACHE
    template_path = BASE_DIR / "app" / "templates" / "index.html"
    if template_path.exists():
        mtime = template_path.stat().st_mtime
        if _INDEX_HTML_CACHE is not None and _INDEX_HTML_CACHE[0] == mtime:
            html_content = _INDEX_HTML_CACHE[1]
        else:
            async with await anyio.open_file(template_path, "r", encoding="utf-8") as f:
                html_content = await f.read()
            _INDEX_HTML_CACHE = (mtime, html_content)
        return HTMLResponse(
            content=html_content,
            headers={"Cache-Control": "no-cache, must-revalidate"}
        )
    return HTMLResponse(content="<h1>KonfiX-Catalog API online. Visit <a href='/docs'>/docs</a>.</h1>")
