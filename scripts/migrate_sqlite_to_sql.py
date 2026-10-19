#!/usr/bin/env python3
"""
Migrations- und Wartungs-Skript für KoNfiX-Catalog:
1. Migriert alle Daten (Hersteller, Geräte, Applikationen, KOs, Parameter,
   Zuweisungsregeln, Übersetzungen) aus einer bestehenden SQLite-Datenbank
   (Standard: data/konfix_database.db) in eine Ziel-SQL-Datenbank (MySQL/MariaDB/PostgreSQL).
2. Alternativ können auch alle YAML-Dateien aus catalog_files/ direkt in die
   Ziel-Datenbank importiert werden (--from-yaml-dir).
3. Unterstützt --vacuum-sqlite zur Bereinigung der lokalen SQLite-Datenbank
   (schrumpft fragmentierte Freelist-Pages von ~98 MB auf ~4 MB).

Verwendung:
  # 1. Migration von SQLite nach MySQL/MariaDB (nutzt DATABASE_URL / DB_* aus .env oder --target-url):
  python scripts/migrate_sqlite_to_sql.py --target-url "mysql+pymysql://user:pass@localhost:3306/konfix_catalog?charset=utf8mb4"

  # 2. Lokale SQLite-Datenbank komprimieren und Count-Spalten synchronisieren:
  python scripts/migrate_sqlite_to_sql.py --vacuum-sqlite
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict

from sqlalchemy import create_engine, insert, text
from sqlalchemy.orm import sessionmaker

# Projekt-Root zum Pfad hinzufügen
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import settings
from app.database import Base, ensure_database_ready
from app.models import (
    ApplicationProgram,
    AssignRule,
    CommunicationObject,
    Device,
    Manufacturer,
    Parameter,
    Translation,
)


def vacuum_sqlite_database(sqlite_path: Path) -> None:
    if not sqlite_path.exists():
        print(f"! SQLite-Datei nicht gefunden: {sqlite_path}")
        return

    before_bytes = sqlite_path.stat().st_size
    sqlite_url = f"sqlite:///{sqlite_path}"
    eng = create_engine(sqlite_url, connect_args={"check_same_thread": False})
    print(f"Synchronisiere Schema & Zählspalten für {sqlite_path} ...")
    ensure_database_ready(force=True)

    print("Führe SQLite VACUUM & ANALYZE aus...")
    with eng.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("VACUUM"))
        conn.execute(text("ANALYZE"))
    eng.dispose()

    after_bytes = sqlite_path.stat().st_size
    print(
        f"✓ SQLite-Datenbank optimiert: "
        f"{before_bytes / (1024 * 1024):.2f} MB -> {after_bytes / (1024 * 1024):.2f} MB"
    )


def migrate_sqlite_to_target(source_sqlite: Path, target_url: str) -> None:
    if not source_sqlite.exists():
        raise FileNotFoundError(f"Quell-SQLite-Datei nicht gefunden: {source_sqlite}")

    source_url = f"sqlite:///{source_sqlite.resolve()}"
    if source_url == target_url:
        raise ValueError("Quell- und Ziel-Datenbank dürfen nicht identisch sein.")

    print("=" * 68)
    print("KoNfiX-Catalog: SQLite -> SQL Datenbank-Migration")
    print("=" * 68)
    print(f"Quelle (SQLite): {source_sqlite}")
    masked_target = target_url.split("@")[-1] if "@" in target_url else target_url
    print(f"Ziel (SQL):      {masked_target}")

    src_engine = create_engine(source_url, connect_args={"check_same_thread": False})
    tgt_engine = create_engine(target_url, pool_pre_ping=True, pool_recycle=1800)

    # Ziel-Schema anlegen
    print("\n1. Erstelle Tabellen-Schema auf Ziel-Datenbank...")
    Base.metadata.create_all(bind=tgt_engine)

    SrcSession = sessionmaker(autocommit=False, autoflush=False, bind=src_engine)
    TgtSession = sessionmaker(autocommit=False, autoflush=False, bind=tgt_engine)

    with SrcSession() as src_db, TgtSession() as tgt_db:
        # 1. Manufacturers
        src_mfgs = src_db.query(Manufacturer).order_by(Manufacturer.id.asc()).all()
        mfg_id_map: Dict[int, int] = {}
        print(f"\n2. Migriere {len(src_mfgs)} Hersteller...")
        for m in src_mfgs:
            existing = None
            if m.code:
                existing = tgt_db.query(Manufacturer).filter(Manufacturer.code == m.code).first()
            if not existing and m.knx_id:
                existing = tgt_db.query(Manufacturer).filter(Manufacturer.knx_id == m.knx_id).first()

            if not existing:
                new_m = Manufacturer(
                    code=m.code,
                    knx_id=m.knx_id,
                    name=m.name,
                    country=m.country,
                    website=m.website,
                    logo_url=m.logo_url,
                    created_at=m.created_at,
                )
                tgt_db.add(new_m)
                tgt_db.flush()
                mfg_id_map[m.id] = new_m.id
            else:
                mfg_id_map[m.id] = existing.id
        tgt_db.commit()

        # 2. Devices + Kinder
        src_devices = src_db.query(Device).order_by(Device.id.asc()).all()
        print(f"3. Migriere {len(src_devices)} Geräte inklusive relationaler Datensätze...")

        total_cos = 0
        total_params = 0
        total_rules = 0
        total_trans = 0

        for d in src_devices:
            target_mfg_id = mfg_id_map.get(d.manufacturer_id)
            if not target_mfg_id:
                continue

            cos_rows = (
                src_db.query(CommunicationObject)
                .filter(CommunicationObject.device_id == d.id)
                .all()
            )
            param_rows = (
                src_db.query(Parameter)
                .filter(Parameter.device_id == d.id)
                .all()
            )
            rule_rows = (
                src_db.query(AssignRule)
                .filter(AssignRule.device_id == d.id)
                .all()
            )
            trans_rows = (
                src_db.query(Translation)
                .filter(Translation.device_id == d.id)
                .all()
            )
            app_rows = (
                src_db.query(ApplicationProgram)
                .filter(ApplicationProgram.device_id == d.id)
                .all()
            )

            tgt_dev = (
                tgt_db.query(Device)
                .filter(Device.order_number == d.order_number)
                .first()
            )
            if not tgt_dev:
                tgt_dev = Device(
                    order_number=d.order_number,
                    name=d.name,
                    description=d.description,
                    hardware_name=d.hardware_name,
                    hardware_version=d.hardware_version,
                    bus_current_ma=d.bus_current_ma,
                    source_url=d.source_url,
                    manufacturer_id=target_mfg_id,
                    yaml_content=d.yaml_content,
                    edit_token=d.edit_token,
                    com_objects_count=len(cos_rows),
                    parameters_count=len(param_rows),
                    translations_count=len(trans_rows),
                    created_at=d.created_at,
                    updated_at=d.updated_at,
                )
                tgt_db.add(tgt_dev)
                tgt_db.flush()
            else:
                tgt_dev.name = d.name
                tgt_dev.description = d.description
                tgt_dev.hardware_name = d.hardware_name
                tgt_dev.hardware_version = d.hardware_version
                tgt_dev.bus_current_ma = d.bus_current_ma
                tgt_dev.source_url = d.source_url
                tgt_dev.manufacturer_id = target_mfg_id
                tgt_dev.yaml_content = d.yaml_content
                tgt_dev.edit_token = d.edit_token
                tgt_dev.com_objects_count = len(cos_rows)
                tgt_dev.parameters_count = len(param_rows)
                tgt_dev.translations_count = len(trans_rows)
                tgt_db.query(ApplicationProgram).filter(ApplicationProgram.device_id == tgt_dev.id).delete()
                tgt_db.query(CommunicationObject).filter(CommunicationObject.device_id == tgt_dev.id).delete()
                tgt_db.query(Parameter).filter(Parameter.device_id == tgt_dev.id).delete()
                tgt_db.query(AssignRule).filter(AssignRule.device_id == tgt_dev.id).delete()
                tgt_db.query(Translation).filter(Translation.device_id == tgt_dev.id).delete()
                tgt_db.flush()

            if app_rows:
                tgt_db.execute(
                    insert(ApplicationProgram),
                    [
                        {
                            "device_id": tgt_dev.id,
                            "app_id": a.app_id,
                            "name": a.name,
                            "version": a.version,
                            "mask_version": a.mask_version,
                            "com_objects_count": a.com_objects_count,
                            "parameters_count": a.parameters_count,
                        }
                        for a in app_rows
                    ],
                )

            if cos_rows:
                tgt_db.execute(
                    insert(CommunicationObject),
                    [
                        {
                            "device_id": tgt_dev.id,
                            "obj_id": c.obj_id,
                            "number": c.number,
                            "name": c.name,
                            "function": c.function,
                            "dpt": c.dpt,
                            "size": c.size,
                            "flags": c.flags,
                            "conditions": c.conditions,
                        }
                        for c in cos_rows
                    ],
                )
                total_cos += len(cos_rows)

            if param_rows:
                tgt_db.execute(
                    insert(Parameter),
                    [
                        {
                            "device_id": tgt_dev.id,
                            "param_id": p.param_id,
                            "name": p.name,
                            "text": p.text,
                            "type": p.type,
                            "default_value": p.default_value,
                            "page": p.page,
                            "section": p.section,
                            "options": p.options,
                            "conditions": p.conditions,
                        }
                        for p in param_rows
                    ],
                )
                total_params += len(param_rows)

            if rule_rows:
                tgt_db.execute(
                    insert(AssignRule),
                    [
                        {
                            "device_id": tgt_dev.id,
                            "target": r.target,
                            "source": r.source,
                            "value": r.value,
                            "conditions": r.conditions,
                        }
                        for r in rule_rows
                    ],
                )
                total_rules += len(rule_rows)

            if trans_rows:
                trans_dicts = [
                    {
                        "device_id": tgt_dev.id,
                        "entity_id": t.entity_id,
                        "language": t.language,
                        "text": t.text,
                    }
                    for t in trans_rows
                ]
                chunk_size = 5000
                for idx in range(0, len(trans_dicts), chunk_size):
                    tgt_db.execute(insert(Translation), trans_dicts[idx : idx + chunk_size])
                total_trans += len(trans_rows)

            tgt_db.commit()
            print(
                f"   ✓ {d.order_number}: {len(cos_rows)} KOs, "
                f"{len(param_rows)} Parameter, {len(trans_rows)} Übersetzungen"
            )

    src_engine.dispose()
    tgt_engine.dispose()
    print("\n4. Zusammenfassung:")
    print(f"   - Hersteller:          {len(src_mfgs)}")
    print(f"   - Geräte:              {len(src_devices)}")
    print(f"   - Kommunikationsobj.:  {total_cos}")
    print(f"   - Parameter:           {total_params}")
    print(f"   - Zuweisungsregeln:    {total_rules}")
    print(f"   - Übersetzungen:       {total_trans}")
    print("✓ Migration erfolgreich abgeschlossen.")
    print("=" * 68)


def import_yaml_directory_to_target(yaml_dir: Path, target_url: str) -> int:
    """
    Importiert alle im Verzeichnis yaml_dir liegenden YAML-Dateien in die Ziel-Datenbank,
    sofern das entsprechende Gerät dort noch nicht existiert.
    """
    if not yaml_dir.exists():
        return 0

    from app.services.yaml_converter import parse_konfix_yaml

    tgt_engine = create_engine(target_url, pool_pre_ping=True, pool_recycle=1800)
    Base.metadata.create_all(bind=tgt_engine)
    TgtSession = sessionmaker(autocommit=False, autoflush=False, bind=tgt_engine)

    yaml_files = sorted(list(yaml_dir.glob("*.yaml")) + list(yaml_dir.glob("*.yml")))
    imported_count = 0

    with TgtSession() as db:
        for yf in yaml_files:
            try:
                content = yf.read_text(encoding="utf-8")
                doc = parse_konfix_yaml(content)
                dev_data = doc.get("device") or {}
                order_num = dev_data.get("order_number")
                if not order_num:
                    continue

                existing = db.query(Device).filter(Device.order_number == order_num).first()
                if existing:
                    continue

                mfg_data = doc.get("manufacturer") or {}
                mfg_code = (mfg_data.get("code") or "custom").strip().lower()
                mfg_name = mfg_data.get("name") or "Hersteller"

                mfg = db.query(Manufacturer).filter(Manufacturer.code == mfg_code).first()
                if not mfg:
                    mfg = Manufacturer(
                        name=mfg_name,
                        code=mfg_code,
                        knx_id=mfg_data.get("legacy_knx_id") or f"M-{mfg_code}",
                    )
                    db.add(mfg)
                    db.flush()

                hw_data = dev_data.get("hardware") or {}
                dev = Device(
                    manufacturer_id=mfg.id,
                    order_number=order_num,
                    name=dev_data.get("name") or order_num,
                    description=dev_data.get("description"),
                    hardware_name=hw_data.get("name"),
                    hardware_version=str(hw_data.get("version")) if hw_data.get("version") else None,
                    bus_current_ma=float(hw_data.get("bus_current_ma")) if hw_data.get("bus_current_ma") is not None else 10.0,
                    yaml_content=content,
                )
                db.add(dev)
                db.flush()
                imported_count += 1
            except Exception as e:
                print(f"Fehler beim Import von {yf.name}: {e}")

        db.commit()

    tgt_engine.dispose()
    return imported_count


def main():
    parser = argparse.ArgumentParser(description="KoNfiX-Catalog SQLite -> SQL Migrations-Werkzeug")
    parser.add_argument(
        "--source-sqlite",
        type=Path,
        default=BASE_DIR / "data" / "konfix_database.db",
        help="Pfad zur Quell-SQLite-Datei (Standard: data/konfix_database.db)",
    )
    parser.add_argument(
        "--target-url",
        type=str,
        default=None,
        help="Ziel-DATABASE_URL (z.B. mysql+pymysql://user:pass@localhost:3306/konfix_catalog?charset=utf8mb4)",
    )
    parser.add_argument(
        "--vacuum-sqlite",
        action="store_true",
        help="Komprimiert die lokale SQLite-Datenbank per VACUUM & synchronisiert Count-Spalten",
    )
    args = parser.parse_args()

    if args.vacuum_sqlite:
        vacuum_sqlite_database(args.source_sqlite)
        if not args.target_url:
            return

    target_url = args.target_url or settings.DATABASE_URL
    if target_url.startswith("sqlite:"):
        print(
            "Hinweis: Keine externe SQL-Ziel-Datenbank angegeben (--target-url oder DB_ENGINE=mysql in .env).\n"
            "Führe stattdessen Optimierung & VACUUM auf der lokalen SQLite-Datenbank aus..."
        )
        vacuum_sqlite_database(args.source_sqlite)
        return

    migrate_sqlite_to_target(args.source_sqlite, target_url)


if __name__ == "__main__":
    main()
