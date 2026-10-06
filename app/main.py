# Standard library
from contextlib import asynccontextmanager

import anyio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import api_v1_router
from app.config import BASE_DIR, settings
from app.database import Base, engine


def init_db():
    # Initialize DB schema immediately
    Base.metadata.create_all(bind=engine)

    # Self-healing migration: Add source_url column if not present in legacy SQLite DBs
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE knxprod_files ADD COLUMN source_url VARCHAR(1024)"))
            conn.commit()
    except Exception:
        pass  # Column already exists

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
            gira_devices = db.query(Device).filter(Device.order_number == "216800").all()
            for dev in gira_devices:
                dev.manufacturer_id = m_0008.id
            db.commit()

        # Populate sample data if DB is completely fresh
        if db.query(Device).count() == 0:
            try:
                from scripts.seed_sample_data import seed_database
                seed_database()
            except Exception as seed_err:
                print("Automatic seed skipped:", seed_err)
    except Exception:
        db.rollback()
    finally:
        db.close()


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

# Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
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

# Root Web Frontend
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_index():
    template_path = BASE_DIR / "app" / "templates" / "index.html"
    if template_path.exists():
        async with await anyio.open_file(template_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=await f.read())
    return HTMLResponse(content="<h1>KonfiX-Catalog API online. Visit <a href='/docs'>/docs</a>.</h1>")
