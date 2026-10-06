import secrets
from fastapi import APIRouter, Depends, Header, HTTPException, status
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication & Administration"])

def get_configured_admin_key() -> str:
    return settings.ADMIN_KEY or settings.API_KEY


def verify_admin_key(
    x_api_key: str | None = Header(None, description="Admin API-Key / Passwort im Header 'X-API-Key'"),
    authorization: str | None = Header(None, description="Admin API-Key / Passwort als Bearer Token")
) -> bool:
    admin_key = get_configured_admin_key()
    if not admin_key:
        # Kein Admin-Key konfiguriert -> Offener Modus (z. B. lokale Entwicklung)
        return True

    token = x_api_key
    if not token and authorization:
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
        else:
            token = authorization.strip()

    if not token or not secrets.compare_digest(token, admin_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungültiger oder fehlender Admin-Key (Header 'X-API-Key' oder 'Authorization: Bearer <token>')"
        )
    return True


# Backward-compatible alias
verify_api_key = verify_admin_key


def verify_upload_permission(
    x_api_key: str | None = Header(None, description="Optionaler Admin-Key für Uploads"),
    authorization: str | None = Header(None, description="Optionaler Bearer Token")
) -> bool:
    if settings.ALLOW_PUBLIC_UPLOAD:
        return True
    return verify_admin_key(x_api_key=x_api_key, authorization=authorization)


@router.get(
    "/verify",
    summary="Verify admin authorization status",
    description="Überprüft, ob ein Admin-Key erforderlich ist und ob der übergebene Key gültig ist."
)
def verify_auth_status(authorized: bool = Depends(verify_admin_key)):
    admin_key = get_configured_admin_key()
    return {
        "status": "authenticated",
        "auth_required": bool(admin_key),
        "message": "Erfolgreich als Administrator autorisiert" if admin_key else "Kein Admin-Key konfiguriert (offener Modus)"
    }

