# Standard library
from contextlib import asynccontextmanager

import anyio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import api_v1_router
from app.config import BASE_DIR, settings
from app.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB schema on startup
    Base.metadata.create_all(bind=engine)

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
    except Exception:
        db.rollback()
    finally:
        db.close()

    yield

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=f"""
{settings.APP_DESCRIPTION}

### Features
* **Zero-Config Upload für Hersteller**: `POST /api/v1/upload` mit `Content-Type: application/octet-stream` (automatische XML-Erkennung).
* **Download per POST**: `POST /api/v1/download` mit Filterkriterien gibt direkt die `.knxprod`-Datei als `application/octet-stream` zurück.
* **Klassischer Download per GET**: `GET /api/v1/download/{{order_number}}`.
* **Geräte- & Herstellersuche**: Volltextsuche und Filterung via `GET /api/v1/devices` und `GET /api/v1/manufacturers`.
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
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
