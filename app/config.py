import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "KonfiX-Catalog"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Open REST Online Database & Catalog for KNX devices (.knxprod)"
    
    # Database
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/data/konfix_catalog.db"
    
    # Storage
    STORAGE_DIR: str = str(BASE_DIR / "catalog_files")
    
    # Security / Upload protection (empty = open upload for all manufacturers)
    API_KEY: str = ""
    
    # CORS
    ALLOWED_ORIGINS: list[str] = ["*"]

settings = Settings()

# Ensure directories exist
os.makedirs(os.path.dirname(settings.DATABASE_URL.replace("sqlite:///", "")), exist_ok=True)
os.makedirs(settings.STORAGE_DIR, exist_ok=True)
