import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import engine, Base, SessionLocal
from app.api.v1.upload import _process_and_save_knxprod
from scripts.create_sample_knxprod import create_sample_knxprod_archive

def seed_database():
    print("Initializing database schema...")
    Base.metadata.create_all(bind=engine)

    samples = [
        ("M-00C5", "MDT technologies", "AKS-0816.04", "Schaltaktor 8-fach 16A", "Schaltaktor Standard", "Schalten 8f 16A", "4.2", "MV-07B0", 12.0),
        ("M-0002", "ABB Stotz-Kontakt GmbH", "SA/S8.16.6.2", "Schaltaktor 8-fach 16A C-Last", "SA/S Aktor", "Schalten 8f 16A C-Last", "2.1", "MV-07B0", 10.0),
        ("M-0083", "Gira Giersiepen GmbH", "216800", "Dimmaktor 4-fach Komfort", "Dimmaktor REG", "Dimmen 4f Komfort", "1.3", "MV-07B0", 15.0),
        ("M-0077", "Theben AG", "RMG 8 S KNX", "Schaltaktor Grundmodul 8-fach", "RMG 8 S", "Schalten RMG 8", "3.0", "MV-07B0", 8.5),
        ("M-0004", "JUNG", "2308 REG HRE", "Schaltaktor 8-fach Handbetätigung", "2308REG", "Schalten 8-fach Standard", "1.1", "MV-07B0", 14.0)
    ]

    db = SessionLocal()
    try:
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
            resp = _process_and_save_knxprod(data, filename, db)
            print(f"Imported: {resp.manufacturer_name} -> {order_no} ({resp.filename}, {resp.file_size_bytes} Bytes)")

        print("Seeding completed successfully!")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
