// KonfiX-Catalog Frontend Logic

let allManufacturers = [];
let searchTimeout = null;

document.addEventListener("DOMContentLoaded", () => {
  loadStats();
  loadManufacturers();
  loadDevices();

  // Search input with debounce
  const searchInput = document.getElementById("searchInput");
  searchInput.addEventListener("input", (e) => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      loadDevices();
    }, 300);
  });

  // Manufacturer filter
  const mfgFilter = document.getElementById("manufacturerFilter");
  mfgFilter.addEventListener("change", () => {
    loadDevices();
  });

  // Upload modal controls
  const openUploadBtn = document.getElementById("openUploadBtn");
  const closeUploadBtn = document.getElementById("closeUploadBtn");
  const uploadModal = document.getElementById("uploadModal");

  openUploadBtn.addEventListener("click", () => uploadModal.classList.add("open"));
  closeUploadBtn.addEventListener("click", () => uploadModal.classList.remove("open"));

  // Detail modal controls
  const detailModal = document.getElementById("detailModal");
  const closeDetailBtn = document.getElementById("closeDetailBtn");
  closeDetailBtn.addEventListener("click", () => detailModal.classList.remove("open"));

  // Drag and drop setup
  setupDropZone();
});

async function loadStats() {
  try {
    const res = await fetch("/api/v1/stats");
    if (!res.ok) return;
    const data = await res.json();
    document.getElementById("statDevices").textContent = data.devices_total;
    document.getElementById("statManufacturers").textContent = data.manufacturers_total;
    document.getElementById("statFiles").textContent = data.files_total;
    document.getElementById("statSize").textContent = `${data.total_catalog_size_mb} MB`;
  } catch (err) {
    console.error("Stats load error:", err);
  }
}

async function loadManufacturers() {
  try {
    const res = await fetch("/api/v1/manufacturers");
    if (!res.ok) return;
    allManufacturers = await res.json();
    const select = document.getElementById("manufacturerFilter");
    select.innerHTML = '<option value="">Alle Hersteller</option>';
    allManufacturers.forEach(mfg => {
      const opt = document.createElement("option");
      opt.value = mfg.knx_id;
      opt.textContent = `${mfg.name} (${mfg.device_count || 0})`;
      select.appendChild(opt);
    });
  } catch (err) {
    console.error("Manufacturers load error:", err);
  }
}

async function loadDevices() {
  const grid = document.getElementById("devicesGrid");
  const q = document.getElementById("searchInput").value.trim();
  const mfg = document.getElementById("manufacturerFilter").value;

  grid.innerHTML = `
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Lade Gerätedaten...</p>
    </div>
  `;

  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (mfg) params.set("manufacturer_id", mfg);

  try {
    const res = await fetch(`/api/v1/devices?${params.toString()}`);
    if (!res.ok) throw new Error("Fehler beim Laden der Geräte");
    const data = await res.json();

    document.getElementById("resultsCount").textContent = `${data.total} Einträge`;

    if (data.devices.length === 0) {
      grid.innerHTML = `
        <div class="loading-state">
          <p>🔍 Keine passenden KNX-Geräte gefunden.</p>
          <small style="color: #64748b; margin-top: 0.5rem; display: block;">
            Lade eine <code>.knxprod</code>-Datei über den Upload-Button hoch oder passe den Suchbegriff an.
          </small>
        </div>
      `;
      return;
    }

    grid.innerHTML = "";
    data.devices.forEach(device => {
      grid.appendChild(createDeviceCard(device));
    });
  } catch (err) {
    grid.innerHTML = `<div class="loading-state"><p>❌ Fehler beim Laden der Daten: ${err.message}</p></div>`;
  }
}

function createDeviceCard(device) {
  const card = document.createElement("div");
  card.className = "device-card";

  const appPills = device.applications.map(app => `
    <span class="app-pill" title="Mask: ${app.mask_version || 'N/A'}, ComObjects: ${app.com_objects_count}">
      ⚙️ ${escapeHtml(app.name)} ${app.version ? 'v' + escapeHtml(app.version) : ''}
    </span>
  `).join("");

  const downloadBtn = device.knxprod_file ? `
    <a href="/api/v1/download/${encodeURIComponent(device.order_number)}" class="btn btn-primary btn-sm" download>
      ⬇️ .knxprod Download
    </a>
  ` : `<span class="badge">Keine Datei</span>`;

  card.innerHTML = `
    <div class="card-top">
      <div>
        <span class="badge badge-mfg">${escapeHtml(device.manufacturer.name)}</span>
      </div>
      <span class="order-badge">${escapeHtml(device.order_number)}</span>
    </div>
    
    <h3 class="card-title">${escapeHtml(device.name)}</h3>
    
    <div class="card-specs">
      ${device.hardware_version ? `<span class="spec-item">HW: <strong>v${escapeHtml(device.hardware_version)}</strong></span>` : ''}
      ${device.bus_current_ma ? `<span class="spec-item">Bus: <strong>${device.bus_current_ma} mA</strong></span>` : ''}
      ${device.knxprod_file ? `<span class="spec-item">Größe: <strong>${formatBytes(device.knxprod_file.file_size_bytes)}</strong></span>` : ''}
    </div>

    <div class="app-list">
      ${appPills || '<small style="color: #64748b;">Keine Applikation angegeben</small>'}
    </div>

    <div class="card-actions">
      ${downloadBtn}
      <button class="btn btn-secondary btn-sm" onclick='showRestDetails(${JSON.stringify(device)})'>
        💻 REST Info
      </button>
    </div>
  `;

  return card;
}

function showRestDetails(device) {
  const modal = document.getElementById("detailModal");
  const title = document.getElementById("modalDeviceTitle");
  const body = document.getElementById("modalDeviceBody");

  const baseUrl = window.location.origin;
  const postCurl = `curl -X POST "${baseUrl}/api/v1/download" \\
  -H "Content-Type: application/json" \\
  -d '{"order_number": "${device.order_number}"}' \\
  --output "${device.order_number}.knxprod"`;

  const getCurl = `curl -L -O "${baseUrl}/api/v1/download/${device.order_number}"`;

  title.textContent = `${device.name} (${device.order_number})`;

  body.innerHTML = `
    <p style="margin-bottom: 1rem; color: #94a3b8;">
      Diese KNX-Produktdatenbank kann direkt per REST-API automatisiert in ETS-Skripte oder CI/CD-Pipelines eingebunden werden.
    </p>

    <h4 style="font-size: 0.95rem; margin-bottom: 0.35rem; color: #f8fafc;">1. Download per POST (application/octet-stream):</h4>
    <div class="code-block">${escapeHtml(postCurl)}</div>

    <h4 style="font-size: 0.95rem; margin-top: 1.25rem; margin-bottom: 0.35rem; color: #f8fafc;">2. Download per GET (application/octet-stream):</h4>
    <div class="code-block">${escapeHtml(getCurl)}</div>

    ${device.knxprod_file ? `
      <div style="margin-top: 1.25rem; font-size: 0.8rem; color: #94a3b8;">
        <strong>SHA256 Prüfsumme:</strong><br>
        <code style="color: #38bdf8; font-family: monospace;">${device.knxprod_file.sha256}</code>
      </div>
    ` : ''}
  `;

  modal.classList.add("open");
}

function setupDropZone() {
  const dropZone = document.getElementById("dropZone");
  const fileInput = document.getElementById("fileInput");
  const uploadProgress = document.getElementById("uploadProgress");
  const uploadSpinner = document.getElementById("uploadSpinner");
  const statusText = document.getElementById("uploadStatusText");
  const resultsList = document.getElementById("uploadResultsList");

  dropZone.addEventListener("click", () => fileInput.click());

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });

  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
  });

  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files.length > 0) {
      handleFilesUpload(Array.from(e.dataTransfer.files));
    }
  });

  fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) {
      handleFilesUpload(Array.from(fileInput.files));
    }
  });

  async function handleFilesUpload(files) {
    if (!files || files.length === 0) return;

    dropZone.style.display = "none";
    uploadProgress.style.display = "block";
    if (uploadSpinner) uploadSpinner.style.display = "block";
    if (resultsList) {
      resultsList.style.display = "none";
      resultsList.innerHTML = "";
    }

    const fileCount = files.length;
    statusText.textContent = fileCount === 1
      ? `Lade '${files[0].name}' hoch und verarbeite...`
      : `Lade ${fileCount} Dateien hoch und verarbeite...`;

    try {
      let data;
      if (fileCount === 1 && !files[0].name.toLowerCase().endsWith(".zip")) {
        // Single knxprod file - send as raw octet-stream to /api/v1/upload
        const file = files[0];
        const res = await fetch("/api/v1/upload", {
          method: "POST",
          headers: {
            "Content-Type": "application/octet-stream",
            "X-File-Name": encodeURIComponent(file.name)
          },
          body: file
        });
        data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Upload fehlgeschlagen");
      } else {
        // Multiple files or ZIP archive - send to /api/v1/upload/batch
        const formData = new FormData();
        for (const file of files) {
          formData.append("files", file);
        }
        const res = await fetch("/api/v1/upload/batch", {
          method: "POST",
          body: formData
        });
        data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Upload fehlgeschlagen");
      }

      if (uploadSpinner) uploadSpinner.style.display = "none";

      if (data.results) {
        // BatchUploadResponse
        const isSuccess = data.status === "success";
        const isPartial = data.status === "partial";
        const statusColor = isSuccess ? "#10b981" : (isPartial ? "#f59e0b" : "#ef4444");
        const statusIcon = isSuccess ? "✓" : (isPartial ? "⚠️" : "❌");

        statusText.innerHTML = `
          <span style="color: ${statusColor}; font-weight: 600;">${statusIcon} ${escapeHtml(data.message)}</span>
        `;

        if (resultsList) {
          resultsList.style.display = "block";
          resultsList.innerHTML = data.results.map(item => {
            const itemSuccess = item.status === "success";
            const badgeClass = itemSuccess ? "success" : "error";
            const badgeText = itemSuccess ? "OK" : "Fehler";
            const devCount = item.devices_imported ? item.devices_imported.length : 0;
            const detail = itemSuccess
              ? `${devCount} Gerät(e) indexiert`
              : escapeHtml(item.message || "Fehler beim Import");

            return `
              <div class="upload-result-item">
                <div>
                  <div class="item-name" title="${escapeHtml(item.filename)}">${escapeHtml(item.filename)}</div>
                  <small style="color: #64748b; font-size: 0.72rem;">${detail}</small>
                </div>
                <span class="item-badge ${badgeClass}">${badgeText}</span>
              </div>
            `;
          }).join("");
        }

      } else {
        // Single UploadResponse
        statusText.innerHTML = `
          <span style="color: #10b981; font-weight: 600;">✓ Erfolgreich importiert!</span><br>
          Hersteller: <strong>${escapeHtml(data.manufacturer_name)}</strong><br>
          Geräte: ${data.devices_imported.map(d => `<code>${escapeHtml(d.order_number)}</code>`).join(", ")}
        `;
      }

      setTimeout(() => {
        document.getElementById("uploadModal").classList.remove("open");
        resetUploadUI();
        loadStats();
        loadManufacturers();
        loadDevices();
      }, data.results && data.results.length > 3 ? 4000 : 2500);

    } catch (err) {
      if (uploadSpinner) uploadSpinner.style.display = "none";
      statusText.innerHTML = `
        <span style="color: #ef4444; font-weight: 600;">❌ Fehler:</span><br>
        ${escapeHtml(err.message)}<br><br>
        <button class="btn btn-secondary btn-sm" onclick="resetUploadUI()">Erneut versuchen</button>
      `;
    }
  }
}

function resetUploadUI() {
  document.getElementById("dropZone").style.display = "block";
  document.getElementById("uploadProgress").style.display = "none";
  const spinner = document.getElementById("uploadSpinner");
  if (spinner) spinner.style.display = "block";
  const resultsList = document.getElementById("uploadResultsList");
  if (resultsList) {
    resultsList.style.display = "none";
    resultsList.innerHTML = "";
  }
  const fileInput = document.getElementById("fileInput");
  if (fileInput) fileInput.value = "";
}


function formatBytes(bytes) {
  if (!bytes) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

function escapeHtml(text) {
  if (!text) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
