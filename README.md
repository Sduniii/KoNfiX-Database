# ⚡ KoNfiX-Database

**Offene REST-Online-Datenbank & Gerätekatalog für KNX-Produktdatenbanken (`.knxprod`)**

KoNfiX-Database ist ein cloud-fähiger REST-Katalogdienst für KNX-Geräte (ähnlich KNXA / ETS Online Catalog). Er ermöglicht es Herstellern und Entwicklern, `.knxprod`-Dateien per REST hochzuladen, nach Geräten zu suchen und diese automatisiert per HTTP GET oder POST herunterzuladen.

---

## 🚀 Kernfunktionen

1. **Ultra-einfacher Upload für Hersteller (`Zero-Config`)**:
   - Upload der rohen `.knxprod`-Binärdatei via `POST /api/v1/upload` (`Content-Type: application/octet-stream`).
   - Keine manuellen Formularfelder erforderlich: Das Backend entpackt das KNX-ZIP und extrahiert Hersteller, Hardware, Bestellnummern und Applikationsprogramme automatisch aus der XML-Struktur (`M-xxxx.xml`).
2. **Download per POST (`application/octet-stream`)**:
   - `POST /api/v1/download` mit JSON-Body (z. B. `{"order_number": "AKS-0816.04"}`) liefert die Datei direkt als Binär-Stream (`application/octet-stream`) zurück.
3. **Klassischer Download per GET**:
   - `GET /api/v1/download/{order_number}` für direkte Verlinkungen oder einfache `curl`-Befehle.
4. **Volltextsuche & Filter**:
   - `GET /api/v1/devices?q=AKS` und `GET /api/v1/manufacturers`.
5. **Modernes Web-Dashboard**:
   - Integrierte Weboberfläche mit Suche, Herstellerfiltern, Spezifikationsansicht und Drag-&-Drop-Upload.
6. **Interaktive Swagger Doku**:
   - Direkt unter `/docs` und ReDoc unter `/redoc`.
7. **Cloud-Ready & GitHub-Integration**:
   - Vorkonfiguriert für kostenloses Hosting auf [Render.com](https://render.com), Fly.io oder Docker via GitHub Actions.

---

## 📡 REST-Schnittstellen Dokumentation

### 1. Upload für Hersteller (`POST /api/v1/upload`)

Hersteller können eine `.knxprod`-Datei per 1-Zeiler hochladen:

```bash
# Upload mit curl als application/octet-stream
curl -X POST "https://deine-app.onrender.com/api/v1/upload" \
     -H "Content-Type: application/octet-stream" \
     -H "X-File-Name: MDT_AKS_081604.knxprod" \
     --data-binary "@MDT_AKS_081604.knxprod"
```

**Antwort (201 Created):**
```json
{
  "status": "success",
  "message": "KNXProd-Datei erfolgreich empfangen, geparst und indexiert",
  "filename": "MDT_AKS_081604.knxprod",
  "file_size_bytes": 1420580,
  "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "manufacturer_id": "M-00C5",
  "manufacturer_name": "MDT technologies",
  "devices_imported": [
    {
      "order_number": "AKS-0816.04",
      "name": "Schaltaktor 8-fach 16A",
      "hardware_version": "2.1",
      "bus_current_ma": 12.0,
      "applications": [
        {
          "name": "Schalten 8f 16A",
          "version": "4.2",
          "mask_version": "MV-07B0",
          "com_objects_count": 4,
          "parameters_count": 2
        }
      ]
    }
  ]
}
```

---

### 2. Download per POST (`POST /api/v1/download`)

Sendet JSON-Kriterien und erhält den Binär-Stream:

```bash
curl -X POST "https://deine-app.onrender.com/api/v1/download" \
     -H "Content-Type: application/json" \
     -d '{"order_number": "AKS-0816.04"}' \
     --output "MDT_AKS_081604.knxprod"
```

**Response Header:**
- `Content-Type: application/octet-stream`
- `Content-Disposition: attachment; filename="MDT_AKS_081604.knxprod"`
- `X-KNX-Order-Number: AKS-0816.04`
- `X-Checksum-SHA256: e3b0c44298...`

---

### 3. Download per GET (`GET /api/v1/download/{order_number}`)

```bash
curl -L -O "https://deine-app.onrender.com/api/v1/download/AKS-0816.04"
```

---

### 4. Geräte abfragen & durchsuchen (`GET /api/v1/devices`)

```bash
# Volltextsuche
curl "https://deine-app.onrender.com/api/v1/devices?q=Schaltaktor"

# Nach Hersteller filtern
curl "https://deine-app.onrender.com/api/v1/devices?manufacturer_id=M-00C5"
```

---

## 🛠️ Lokale Installation & Ausführung

### Voraussetzungen
- Python 3.10+ (oder Docker)

### Schnellstart mit Python:
```bash
# 1. Repository klonen
git clone git@github.com:Sduniii/KoNfiX-Database.git
cd KoNfiX-Database

# 2. Virtual Environment einrichten & Abhängigkeiten installieren
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Beispieldaten erzeugen & importieren
python scripts/seed_sample_data.py

# 4. Server starten
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Öffne jetzt deinen Browser:
- **Web-Katalog**: `http://localhost:8000`
- **Swagger API-Dokumentation**: `http://localhost:8000/docs`

### Schnellstart mit Docker:
```bash
docker compose up --build -d
```

---

## ☁️ Kostenloses Hosting über GitHub (z. B. auf Render.com)

Du brauchst **keine eigene Domain** und **keinen eigenen Server**!

1. Erstelle das GitHub-Repository `KoNfiX-Database` und pushe diesen Code:
   ```bash
   git remote add origin git@github.com:Sduniii/KoNfiX-Database.git
   git push -u origin main
   ```
2. Registriere dich kostenlos auf **[Render.com](https://render.com)** mit deinem GitHub-Account.
3. Klicke auf **New +** > **Blueprint** und wähle dein Repository `KoNfiX-Database` aus.
4. Render erkennt die Datei `render.yaml` vollautomatisch und deployt deinen Service unter einer kostenlosen HTTPS-URL (z. B. `https://konfix-database.onrender.com`).
5. Jeder zukünftige `git push` aktualisiert die Anwendung vollautomatisch.

---

## 🧪 Tests ausführen

```bash
pytest -v
```

Die Testsuite deckt ab:
- Parsing valider KNX-ZIP/XML-Archive (`M-xxxx.xml`)
- Fehlerbehandlung bei beschädigten Dateien
- Upload via `POST /api/v1/upload` (`application/octet-stream`)
- Download via `POST /api/v1/download` (`application/octet-stream`) mit SHA256-Integritätsprüfung
- REST-Such- und Filterendpunkte

---

## 📄 Lizenz

Dieses Projekt steht unter der **GNU Affero General Public License v3.0 (AGPL-3.0)** — siehe [LICENSE](LICENSE) für Details (identisch mit dem Hauptprojekt [KoNfiX](https://github.com/Sduniii/KoNfiX)).
