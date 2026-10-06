import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import engine, Base, SessionLocal
from app.models import Device
from app.api.v1.upload import _process_single_knxprod
from scripts.create_sample_knxprod import create_sample_knxprod_archive

def seed_database(force: bool = False):
    print("Initializing database schema...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        existing_count = db.query(Device).count()
        if existing_count > 0 and not force:
            print(f"Database already contains {existing_count} devices. Skipping demo seed.")
            return

        samples = [
            ("M-0083", "MDT technologies", "AKS-0816.04", "Schaltaktor 8-fach 16A", "Schaltaktor Standard", "Schalten 8f 16A", "4.2", "MV-07B0", 12.0),
            ("M-0002", "ABB Stotz-Kontakt GmbH", "SA/S8.16.6.2", "Schaltaktor 8-fach 16A C-Last", "SA/S Aktor", "Schalten 8f 16A C-Last", "2.1", "MV-07B0", 10.0),
            ("M-0008", "GIRA Giersiepen", "216800", "Dimmaktor 4-fach Komfort", "Dimmaktor REG", "Dimmen 4f Komfort", "1.3", "MV-07B0", 15.0),
            ("M-0048", "Theben AG", "RMG 8 S KNX", "Schaltaktor Grundmodul 8-fach", "RMG 8 S", "Schalten RMG 8", "3.0", "MV-07B0", 8.5),
            ("M-0004", "Albrecht Jung", "2308 REG HRE", "Schaltaktor 8-fach Handbetätigung", "2308REG", "Schalten 8-fach Standard", "1.1", "MV-07B0", 14.0),
            ("M-00FA", "OpenKNX", "OKNX-MOD-01", "OpenKNX Universal Modul", "OpenKNX Hardware", "OpenKNX Firmware", "1.0", "MV-07B0", 5.0)
        ]

        for mfg_id, mfg_name, order_no, prod_name, hw_name, app_name, app_ver, mask, bus in samples:
            filename = f"{mfg_id}_{order_no.replace('/', '_')}.knxprod"
            data = create_sample_knxprod_archive(
                mfg_id=mfg_id,
                mfg_name=mfg_name,
                order_number=order_no,
                product_name=prod_name,
                hardware_name=hw_name,
                app_name=app_name,
                app_version=app_ver,
                mask_version=mask,
                bus_current_ma=bus
            )
            resp = _process_single_knxprod(data, filename, db)
            print(f"Imported: {resp.manufacturer_name} -> {order_no} ({resp.filename}, {resp.file_size_bytes} Bytes)")

        print("Seeding completed successfully!")
    finally:
        db.close()

if __name__ == "__main__":
    force_seed = "--force" in sys.argv
    seed_database(force=force_seed)
