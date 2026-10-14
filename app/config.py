import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    """
    Zentrale Anwendungskonfiguration für KoNfiX-Database & Catalog.

    PRIORITÄT DER EINSTELLUNGEN:
    1. Umgebungsvariablen des Betriebssystems / Docker / Hosting (höchste Priorität)
    2. Datei '.env' im Projekt-Wurzelverzeichnis (falls vorhanden)
    3. Datei '.env.local' im Projekt-Wurzelverzeichnis (für lokale Overrides)
    4. Hier definierte Python-Standardwerte (Fallback, niedrigste Priorität)

    WICHTIG:
    - Alle Werte können ohne Modifikation dieser Datei über eine '.env'-Datei überschrieben werden.
    - Die '.env'-Datei wird von Git ignoriert (.gitignore), sodass vertrauliche Passwörter
      niemals im Git-Repository landen und bei einem 'git pull' nicht überschrieben werden.
    """
    model_config = SettingsConfigDict(
        env_file=(
            BASE_DIR / ".env",
            BASE_DIR / ".env.local",
            ".env",
            ".env.local",
        ),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # ==========================================================================
    # 1. Anwendung & URLs
    # ==========================================================================
    # Name der Anwendung in UI, Swagger-Dokumentation und OpenAPI
    # Beispiel in .env: APP_NAME=KoNfiX-Database
    APP_NAME: str = "KoNfiX-Database"

    # Semantische Version der laufenden Catalog-Instanz
    # Beispiel in .env: APP_VERSION=1.0.0
    APP_VERSION: str = "1.0.0"

    # Beschreibungstext für OpenAPI/Swagger
    # Beispiel in .env: APP_DESCRIPTION="Open REST Online Database & Catalog for KNX devices (.knxprod)"
    APP_DESCRIPTION: str = "Open REST Online Database & Catalog for KNX devices (.knxprod)"

    # Öffentliche Basis-URL der laufenden Instanz (ohne abschließenden Slash)
    # Wird für kanonische Links, Schemas und API-Referenzen genutzt
    # Beispiele in .env:
    #   PUBLIC_BASE_URL=https://db.konfix.sduni.de
    #   PUBLIC_BASE_URL=http://localhost:8000
    PUBLIC_BASE_URL: str = "https://db.konfix.sduni.de"

    # Offizielle URL zum validierenden JSON-Schema (v1)
    # Wird in generierten YAML-Dateien und im Starter-Template als $schema hinterlegt
    # Beispiele in .env:
    #   SCHEMA_URL=https://db.konfix.sduni.de/schemas/konfix-device-v1.json
    SCHEMA_URL: str = "https://db.konfix.sduni.de/schemas/konfix-device-v1.json"

    # ==========================================================================
    # 2. Datenbank-Verbindung
    # ==========================================================================
    # SQLAlchemy-kompatibler Connection-String
    # Beispiele in .env:
    #   DATABASE_URL=sqlite:///./data/konfix_database.db                        (Standard SQLite)
    #   DATABASE_URL=sqlite:////var/data/konfix_database.db                     (Absoluter Pfad / Render / Docker)
    #   DATABASE_URL=postgresql://konfix_user:geheim123@localhost:5432/konfix  (PostgreSQL Produktion)
    #   DATABASE_URL=mysql+pymysql://konfix_user:pass@127.0.0.1:3306/konfix     (MySQL / MariaDB)
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/data/konfix_database.db"

    # ==========================================================================
    # 3. Dateispeicher (Katalog-Archive & YAMLs)
    # ==========================================================================
    # Lokaler Verzeichnispfad, in dem .knxprod- und .yaml-Dateien gespeichert werden
    # Beispiele in .env:
    #   STORAGE_DIR=./catalog_files
    #   STORAGE_DIR=/var/data/catalog_files                                     (Docker / Persistent Volume)
    STORAGE_DIR: str = str(BASE_DIR / "catalog_files")

    # ==========================================================================
    # 4. Sicherheit, Admin-Zugang & Berechtigungskontrolle
    # ==========================================================================
    # Geheimer Admin-Schlüssel für geschützte Aktionen.
    # VERHALTEN / SCHUTZWIRKUNG:
    # - Wenn ADMIN_KEY gesetzt ist:
    #   * DELETE /api/v1/devices/{order_number} erfordert zwingend den Admin-Key (HTTP 401 bei Fehlen).
    #   * POST /api/v1/devices/batch-delete erfordert zwingend den Admin-Key.
    #   * PATCH /api/v1/devices/{order_number} ohne gerätespezifischen edit_code erfordert den Admin-Key.
    #   * Admin-Authentifizierung via Header 'X-API-Key: <key>' oder 'Authorization: Bearer <key>'.
    # - Wenn ADMIN_KEY leer ist:
    #   * Der Katalog läuft im offenen Entwicklungs-Modus (Open Mode).
    # Beispiele in .env:
    #   ADMIN_KEY=sicheres-admin-passwort-123456
    ADMIN_KEY: str = ""

    # Abwärtskompatibler Alias für ADMIN_KEY (wird genutzt, falls ADMIN_KEY leer ist)
    # Beispiel in .env: API_KEY=sicheres-admin-passwort-123456
    API_KEY: str = ""

    # Regelt, wer neue Geräte hochladen darf
    # - true:  Jeder Besucher darf neue Geräte importieren (erhält dafür einen edit_code)
    # - false: Uploads sind gesperrt und erfordern zwingend den ADMIN_KEY
    # Beispiel in .env: ALLOW_PUBLIC_UPLOAD=true  (oder false für private Instanzen)
    ALLOW_PUBLIC_UPLOAD: bool = True

    # Automatisches Laden von Demo-Geräten beim allerersten Serverstart (nur bei leerer DB)
    # Beispiel in .env: AUTO_SEED_DEMO_DATA=false (in Produktion immer false)
    AUTO_SEED_DEMO_DATA: bool = False

    # ==========================================================================
    # 5. Upload-Limits & DoS-Schutz (in Bytes bzw. Anzahlen)
    # ==========================================================================
    # Maximale Dateigröße für Uploads in Bytes (Standard: 50 MB = 52.428.800 Bytes)
    # Beispiele in .env:
    #   MAX_UPLOAD_SIZE_BYTES=52428800    (50 MB)
    #   MAX_UPLOAD_SIZE_BYTES=104857600   (100 MB)
    MAX_UPLOAD_SIZE_BYTES: int = 50 * 1024 * 1024

    # Maximale Gesamtgröße des entpackten ZIP-Inhalts (Schutz vor Zip-Bomben)
    # Beispiel in .env: MAX_ZIP_EXTRACTED_BYTES=209715200  (200 MB)
    MAX_ZIP_EXTRACTED_BYTES: int = 200 * 1024 * 1024

    # Maximale Anzahl an Dateien in einem hochgeladenen .knxprod / .zip Archiv
    # Beispiel in .env: MAX_ZIP_FILES=500
    MAX_ZIP_FILES: int = 500

    # Maximale Größe einer einzelnen XML-Datei im Archiv (Schutz vor XML-Entity-Expansion)
    # Beispiel in .env: MAX_XML_PARSE_BYTES=209715200  (200 MB)
    MAX_XML_PARSE_BYTES: int = 200 * 1024 * 1024

    # ==========================================================================
    # 6. CORS & Netzwerk-Schnittstellen
    # ==========================================================================
    # Erlaubte Origins für Cross-Origin Resource Sharing (JSON-Array)
    # Beispiele in .env:
    #   ALLOWED_ORIGINS=["*"]                                                  (Offener API-Zugriff)
    #   ALLOWED_ORIGINS=["https://db.konfix.sduni.de", "http://localhost:8000"] (Eingeschränkter Zugriff)
    ALLOWED_ORIGINS: list[str] = ["*"]

    # Ob CORS-Cookies / Credentials mitgesendet werden dürfen
    # Wichtig: Gemäß CORS-Standard darf dies bei ALLOWED_ORIGINS=["*"] nicht True sein.
    # Beispiel in .env: CORS_ALLOW_CREDENTIALS=false
    CORS_ALLOW_CREDENTIALS: bool = False

    # ==========================================================================
    # 7. Rechtliche Angaben & Compliance
    # ==========================================================================
    # Kontaktadresse für Notice-and-Takedown-Verfahren nach § 23 MarkenG
    # Beispiel in .env: LEGAL_CONTACT_EMAIL=legal@konfix.sduni.de
    LEGAL_CONTACT_EMAIL: str = "legal@konfix.sduni.de"

    # Wenn true, leitet GET /api/v1/download/{order_number} per HTTP 302 direkt
    # zur hinterlegten offiziellen Hersteller-URL weiter, statt die lokale Datei auszuliefern.
    # Beispiel in .env: PREFER_SOURCE_REDIRECT=false
    PREFER_SOURCE_REDIRECT: bool = False

    # Optionale kommagetrennte Passwörter zur Entschlüsselung proprietärer Legacy-Archive (.vd5)
    # Beispiel in .env: KNX_LEGACY_PASSWORDS=herstellerPasswort1,firmenschluessel2
    KNX_LEGACY_PASSWORDS: str = ""

    # ==========================================================================
    # 8. OpenKNX.Toolbox Integration
    # ==========================================================================
    OPENKNX_CACHE_DIR: Path = BASE_DIR / "data" / "openknx_cache"
    OPENKNX_APPLICATIONS_URL: str = "https://go.openknx.de/toolbox-data-applications"
    OPENKNX_RELEASES_URL: str = "https://go.openknx.de/toolbox-data-releases"
    OPENKNX_CACHE_TTL_SECONDS: int = 3600
    KNX_DEFAULT_GATEWAY_IP: str = "127.0.0.1"
    KNX_DEFAULT_GATEWAY_PORT: int = 3671

    # ==========================================================================
    # Dynamische Helper-Properties
    # ==========================================================================
    @property
    def knx_legacy_passwords_bytes(self) -> list[bytes]:
        """Gibt die konfigurierten Passwörter als Liste von UTF-8-Bytefolgen zurück."""
        if not self.KNX_LEGACY_PASSWORDS:
            return []
        return [p.strip().encode("utf-8") for p in self.KNX_LEGACY_PASSWORDS.split(",") if p.strip()]

    @property
    def cors_credentials_safe(self) -> bool:
        """Verhindert ungültige CORS-Kombinationen aus Wildcard-Origin und Credentials."""
        if "*" in self.ALLOWED_ORIGINS:
            return False
        return self.CORS_ALLOW_CREDENTIALS


settings = Settings()

# Verzeichnisse für Datenbank und Dateispeicher bei Bedarf automatisch initialisieren
os.makedirs(os.path.dirname(settings.DATABASE_URL.replace("sqlite:///", "")), exist_ok=True)
os.makedirs(settings.STORAGE_DIR, exist_ok=True)
os.makedirs(settings.OPENKNX_CACHE_DIR, exist_ok=True)
