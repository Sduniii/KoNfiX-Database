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
    
    # Security / Upload protection (empty = open upload for all manufacturers)
    API_KEY: str = ""
    
    # Upload & DoS Protection Limits
    MAX_UPLOAD_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB
    MAX_ZIP_EXTRACTED_BYTES: int = 200 * 1024 * 1024  # 200 MB total uncompressed
    MAX_ZIP_FILES: int = 500  # Max entries in a zip archive
    MAX_XML_PARSE_BYTES: int = 20 * 1024 * 1024  # 20 MB max single XML file
    
    # CORS
    ALLOWED_ORIGINS: list[str] = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = False

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
