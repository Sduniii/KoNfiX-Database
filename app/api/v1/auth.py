import secrets
from fastapi import APIRouter, Depends, Header, HTTPException, status
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication & Administration"])

def verify_api_key(
    x_api_key: str | None = Header(None, description="Admin API-Key im Header 'X-API-Key'"),
    authorization: str | None = Header(None, description="Admin API-Key als Bearer Token")
) -> bool:
    if not settings.API_KEY:
        return True

    token = x_api_key
    if not token and authorization:
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
        else:
            token = authorization.strip()

    if not token or not secrets.compare_digest(token, settings.API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungültiger oder fehlender API-Key (Header 'X-API-Key' oder 'Authorization: Bearer <token>')"
        )
    return True


@router.get(
    "/verify",
    summary="Verify admin authorization status",
    description="Überprüft, ob ein Admin-Key erforderlich ist und ob der übergebene Key gültig ist."
)
def verify_auth_status(authorized: bool = Depends(verify_api_key)):
    return {
        "status": "authenticated",
        "auth_required": bool(settings.API_KEY),
        "message": "Erfolgreich als Administrator autorisiert" if settings.API_KEY else "Kein API-Key konfiguriert (offener Modus)"
    }
