from __future__ import annotations

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/schema", tags=["schema"])

SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "static" / "schemas" / "konfix-device-v1.json"
TEMPLATE_PATH = Path(__file__).resolve().parent.parent.parent / "static" / "schemas" / "konfix-template.yaml"

@router.get("/konfix-device-v1.json", response_class=JSONResponse)
def get_konfix_device_schema(
    download: bool = Query(False, description="Wenn True, wird das Schema als Download-Datei bereitgestellt")
):
    """
    Returns the official KoNfiX Device Definition JSON Schema (v1).
    Used for IDE autocompletion, schema validation, and tool integration.
    """
    if not SCHEMA_PATH.exists():
        raise HTTPException(status_code=404, detail="Schema file not found")
    try:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        headers = {
            "Cache-Control": "public, max-age=86400",
            "Content-Type": "application/schema+json",
        }
        if download:
            headers["Content-Disposition"] = 'attachment; filename="konfix-device-v1.json"'
        return JSONResponse(
            content=data,
            headers=headers
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Laden des Schemas: {e}")


@router.get("/template.yaml")
@router.get("/konfix-template.yaml")
def get_konfix_template_yaml():
    """
    Returns an official, commented starter YAML template for KoNfiX devices.
    """
    if not TEMPLATE_PATH.exists():
        raise HTTPException(status_code=404, detail="Template file not found")
    try:
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        return Response(
            content=content,
            media_type="text/yaml; charset=utf-8",
            headers={
                "Cache-Control": "public, max-age=86400",
                "Content-Disposition": 'attachment; filename="konfix-template.yaml"',
                "Content-Type": "text/yaml; charset=utf-8"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Laden des Templates: {e}")

