import os
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import settings
from app.database import Base, engine, SessionLocal
from app.models import Device, Manufacturer, KnxprodFile, ApplicationProgram


def reset_database(seed: bool = False, keep_files: bool = False):
    print("=" * 60)
    print("KoNfiX-Catalog: Datenbank & Speicher bereinigen")
    print("=" * 60)

    # 1. Tabellen verwerfen und sauber neu erstellen
    print("\n1. Bereinige Datenbanktabellen...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("   ✓ Alle Datenbanktabellen neu initialisiert.")

    # 2. Entferne veraltete DB-Artefakte, falls vorhanden
    legacy_db = BASE_DIR / "data" / "konfix_catalog.db"
    if legacy_db.exists():
        try:
            legacy_db.unlink()
            print("   ✓ Veraltete Datenbankdatei data/konfix_catalog.db entfernt.")
        except Exception as e:
            print(f"   ! Konnte data/konfix_catalog.db nicht löschen: {e}")

    # 3. Bereinige physische Dateien im catalog_files Verzeichnis
    storage_dir = Path(settings.STORAGE_DIR)
    if not keep_files and storage_dir.exists():
        print(f"\n2. Bereinige Dateispeicher ({storage_dir})...")
        deleted_files = 0
        for item in storage_dir.iterdir():
            if item.is_file() and item.name != ".gitkeep":
                try:
                    item.unlink()
                    deleted_files += 1
                except Exception as e:
                    print(f"   ! Fehler beim Löschen von {item.name}: {e}")
        print(f"   ✓ {deleted_files} physische .knxprod-Dateien entfernt (.gitkeep behalten).")

    # 4. Prüfe Zähler
    db = SessionLocal()
    try:
        dev_count = db.query(Device).count()
        mfg_count = db.query(Manufacturer).count()
        file_count = db.query(KnxprodFile).count()
        print("\n3. Status der neuen Datenbank:")
        print(f"   - Geräte (devices):            {dev_count}")
        print(f"   - Hersteller (manufacturers):  {mfg_count}")
        print(f"   - Dateieinträge (files):       {file_count}")
    finally:
        db.close()

    # 5. Optionales Seeding falls gewünscht
    if seed:
        print("\n4. Führe Demo-Seed aus (--seed angegeben)...")
        from scripts.seed_sample_data import seed_database
        seed_database()
    else:
        print("\n✓ Datenbank ist nun vollständig leer und bereit für den Produktivbetrieb.")
    print("=" * 60)


if __name__ == "__main__":
    seed_flag = "--seed" in sys.argv
    keep_files_flag = "--keep-files" in sys.argv
    reset_database(seed=seed_flag, keep_files=keep_files_flag)
