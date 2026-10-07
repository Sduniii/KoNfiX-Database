from __future__ import annotations

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/schema", tags=["schema"])

SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "static" / "schemas" / "konfix-device-v1.json"

@router.get("/konfix-device-v1.json", response_class=JSONResponse)
def get_konfix_device_schema():
    """
    Returns the official KoNfiX Device Definition JSON Schema (v1).
    Used for IDE autocompletion, schema validation, and tool integration.
    """
    if not SCHEMA_PATH.exists():
        raise HTTPException(status_code=404, detail="Schema file not found")
    try:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return JSONResponse(
            content=data,
            headers={
                "Cache-Control": "public, max-age=86400",
                "Content-Type": "application/schema+json",
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Laden des Schemas: {e}")
