#!/usr/bin/env python3
"""
CLI helper to initialize or verify the KoNfiX SQLite database.
Usage:
  python scripts/init_database.py
  python scripts/init_database.py --clean
"""
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import settings
from app.database import Base, engine, SessionLocal, ensure_database_ready, get_sqlite_path
from app.models import (
    Device,
    Manufacturer,
    ApplicationProgram,
    CommunicationObject,
    Parameter,
    AssignRule,
    Translation,
)


def init_database(clean: bool = False):
    print("=" * 60)
    print("KoNfiX-Catalog: Datenbank-Initialisierung")
    print("=" * 60)

    db_path = get_sqlite_path()
    print(f"Konfigurierte SQLite-Datei: {db_path}")

    if clean and db_path and db_path.exists():
        print("\n1. Bereinige bestehende Datenbank (--clean)...")
        try:
            engine.dispose()
            db_path.unlink()
            print("   ✓ Bestehende Datenbankdatei gelöscht.")
        except Exception as e:
            print(f"   ! Konnte Datei nicht löschen: {e}")

    print("\n2. Initialisiere Datenbank & Tabellen...")
    ensure_database_ready()

    if db_path and db_path.exists():
        size_bytes = db_path.stat().st_size
        print(f"   ✓ Datei bereitgestellt ({size_bytes} Bytes)")
    else:
        print("   ! WARNUNG: Datei wurde nicht auf Festplatte gefunden!")

    # Check tables & counts
    db = SessionLocal()
    try:
        dev_count = db.query(Device).count()
        mfg_count = db.query(Manufacturer).count()
        app_count = db.query(ApplicationProgram).count()
        ko_count = db.query(CommunicationObject).count()
        param_count = db.query(Parameter).count()
        rule_count = db.query(AssignRule).count()
        trans_count = db.query(Translation).count()
        print("\n3. Tabellen-Status:")
        print(f"   - Geräte (devices):                     {dev_count}")
        print(f"   - Hersteller (manufacturers):           {mfg_count}")
        print(f"   - Applikationen (application_programs): {app_count}")
        print(f"   - KO-Objekte (communication_objects):   {ko_count}")
        print(f"   - Parameter (parameters):               {param_count}")
        print(f"   - Zuweisungsregeln (assign_rules):      {rule_count}")
        print(f"   - Übersetzungen (translations):         {trans_count}")
    finally:
        db.close()

    print("\n✓ Datenbank ist einsatzbereit.")
    print("=" * 60)


if __name__ == "__main__":
    clean_flag = "--clean" in sys.argv
    init_database(clean=clean_flag)
