import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "KoNfiX-Database"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Open REST Online Database & Catalog for KNX devices (.knxprod)"
    
    # Database
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/data/konfix_database.db"
    
    # Storage
    STORAGE_DIR: str = str(BASE_DIR / "catalog_files")
    
    # Security / Admin & Upload settings
    ADMIN_KEY: str = ""  # If set, required for PATCH/DELETE and batch-delete
    API_KEY: str = ""    # Legacy fallback for ADMIN_KEY
    ALLOW_PUBLIC_UPLOAD: bool = True  # If True, uploads do not require any key
    AUTO_SEED_DEMO_DATA: bool = False  # Set to True to automatically populate demo devices on boot

    
    # Upload & DoS Protection Limits
    MAX_UPLOAD_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB
    MAX_ZIP_EXTRACTED_BYTES: int = 200 * 1024 * 1024  # 200 MB total uncompressed
    MAX_ZIP_FILES: int = 500  # Max entries in a zip archive
    MAX_XML_PARSE_BYTES: int = 20 * 1024 * 1024  # 20 MB max single XML file
    
    # CORS
    ALLOWED_ORIGINS: list[str] = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = False

    # Legal & Compliance
    LEGAL_CONTACT_EMAIL: str = "legal@konfix.sduni.de"
    PREFER_SOURCE_REDIRECT: bool = False
    # Optional comma-separated passwords for legacy archive decryption (.env)
    KNX_LEGACY_PASSWORDS: str = ""

    @property
    def knx_legacy_passwords_bytes(self) -> list[bytes]:
        if not self.KNX_LEGACY_PASSWORDS:
            return []
        return [p.strip().encode("utf-8") for p in self.KNX_LEGACY_PASSWORDS.split(",") if p.strip()]

    @property
    def cors_credentials_safe(self) -> bool:
        # According to CORS spec, allow_credentials cannot be True if '*' is in allowed origins
        if "*" in self.ALLOWED_ORIGINS:
            return False
        return self.CORS_ALLOW_CREDENTIALS


settings = Settings()

# Ensure directories exist
os.makedirs(os.path.dirname(settings.DATABASE_URL.replace("sqlite:///", "")), exist_ok=True)
os.makedirs(settings.STORAGE_DIR, exist_ok=True)
