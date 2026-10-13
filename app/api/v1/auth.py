import secrets
from fastapi import APIRouter, Depends, Header, HTTPException, status
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication & Administration"])

def get_configured_admin_key() -> str:
    """Gibt den auf dem Server hinterlegten Admin-Schlüssel zurück (oder leer)."""
    return (settings.ADMIN_KEY or settings.API_KEY or "").strip()


def is_admin_authenticated(
    x_api_key: str | None = None,
    authorization: str | None = None
) -> bool:
    """
    Prüft, ob der Aufrufer valide Admin-Rechte besitzt.
    
    REGEL:
    - Wenn kein Admin-Key auf dem Server konfiguriert ist (Passwort leer):
      Admin-Modus ist standardmäßig strikt AUS (False). Niemand ist automatisch Admin!
    - Wenn ein Admin-Key konfiguriert ist:
      Muss der übergebene Token exakt mit dem konfigurierten Key übereinstimmen.
    """
    admin_key = get_configured_admin_key()
    if not admin_key:
        return False

    token = x_api_key
    if not token and authorization:
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
        else:
            token = authorization.strip()

    if not token:
        return False
    return secrets.compare_digest(token, admin_key)


def is_admin_request(
    x_api_key: str | None = None,
    authorization: str | None = None
) -> bool:
    """Synonym für is_admin_authenticated zur Berechtigungsprüfung."""
    return is_admin_authenticated(x_api_key=x_api_key, authorization=authorization)


def verify_admin_key(
    x_api_key: str | None = Header(None, description="Admin API-Key / Passwort im Header 'X-API-Key'"),
    authorization: str | None = Header(None, description="Admin API-Key / Passwort als Bearer Token")
) -> bool:
    """FastAPI-Dependency: Verlangt zwingend valide Admin-Authentifizierung."""
    if not is_admin_authenticated(x_api_key=x_api_key, authorization=authorization):
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
    """Prüft, ob Uploads öffentlich erlaubt sind oder Admin-Rechte erfordern."""
    if settings.ALLOW_PUBLIC_UPLOAD:
        return True
    return verify_admin_key(x_api_key=x_api_key, authorization=authorization)


@router.get(
    "/verify",
    summary="Verify admin authorization status",
    description="Überprüft, ob ein Admin-Key konfiguriert ist und ob der übergebene Key gültig ist."
)
def verify_auth_status(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    authorization: str | None = Header(None)
):
    """
    Status-Endpunkt für das Web-Frontend:
    - Wenn auf dem Server kein Key hinterlegt ist: status='unconfigured', is_admin=False.
    - Wenn Key hinterlegt ist und übereinstimmt: status='authenticated', is_admin=True.
    - Wenn Key hinterlegt ist, aber falsch/fehlt: HTTP 401 Unauthorized.
    """
    admin_key = get_configured_admin_key()
    if not admin_key:
        return {
            "status": "unconfigured",
            "is_admin": False,
            "auth_required": False,
            "message": "Kein Admin-Passwort auf dem Server konfiguriert. Admin-Modus ist deaktiviert."
        }

    if is_admin_authenticated(x_api_key=x_api_key, authorization=authorization):
        return {
            "status": "authenticated",
            "is_admin": True,
            "auth_required": True,
            "message": "Erfolgreich als Administrator autorisiert"
        }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Ungültiger oder fehlender Admin-Key (Header 'X-API-Key' oder 'Authorization: Bearer <token>')"
    )
