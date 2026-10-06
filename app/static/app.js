// KoNfiX-Catalog Frontend Logic

let allManufacturers = [];
let searchTimeout = null;
let isAdmin = false;
let currentDeleteOrderNumber = null;

// Auth Helpers
function getAdminKey() {
  return sessionStorage.getItem("konfix_admin_key") || "";
}

function setAdminKey(key) {
  if (key) {
    sessionStorage.setItem("konfix_admin_key", key);
  } else {
    sessionStorage.removeItem("konfix_admin_key");
  }
}

function getAuthHeaders(extraHeaders = {}) {
  const headers = { ...extraHeaders };
  const key = getAdminKey();
  if (key) {
    headers["X-API-Key"] = key;
  }
  return headers;
}

document.addEventListener("DOMContentLoaded", () => {
  initAdminAuth();
  loadStats();
  loadManufacturers();
  loadDevices();

  // Search input with debounce
  const searchInput = document.getElementById("searchInput");
  searchInput.addEventListener("input", () => {
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

  openUploadBtn.addEventListener("click", () => {
    resetUploadUI();
    uploadModal.classList.add("open");
  });
  closeUploadBtn.addEventListener("click", () => uploadModal.classList.remove("open"));

  // Detail modal controls
  const detailModal = document.getElementById("detailModal");
  const closeDetailBtn = document.getElementById("closeDetailBtn");
  closeDetailBtn.addEventListener("click", () => detailModal.classList.remove("open"));

  // Legal modal controls
  const legalModal = document.getElementById("legalModal");
  const openLegalBtn = document.getElementById("openLegalBtn");
  const closeLegalBtn = document.getElementById("closeLegalBtn");
  if (openLegalBtn && legalModal) {
    openLegalBtn.addEventListener("click", () => legalModal.classList.add("open"));
  }
  if (closeLegalBtn && legalModal) {
    closeLegalBtn.addEventListener("click", () => legalModal.classList.remove("open"));
  }

  // Setup Modals & Tabs
  setupUploadTabs();
  setupDropZone();
  setupUrlImport();
  setupEditModal();
  setupDeleteModal();
});

// Admin Authentication Setup
async function initAdminAuth() {
  const adminToggleBtn = document.getElementById("adminToggleBtn");
  const adminAuthModal = document.getElementById("adminAuthModal");
  const closeAdminAuthBtn = document.getElementById("closeAdminAuthBtn");
  const cancelAdminAuthBtn = document.getElementById("cancelAdminAuthBtn");
  const submitAdminAuthBtn = document.getElementById("submitAdminAuthBtn");
  const adminKeyInput = document.getElementById("adminKeyInput");
  const adminAuthError = document.getElementById("adminAuthError");

  // Check initial status
  await checkAdminStatus();

  adminToggleBtn.addEventListener("click", async () => {
    if (isAdmin) {
      if (confirm("Admin-Modus beenden und abmelden?")) {
        setAdminKey("");
        isAdmin = false;
        renderAdminUI();
        loadDevices();
      }
    } else {
      adminKeyInput.value = "";
      adminAuthError.style.display = "none";
      adminAuthModal.classList.add("open");
      adminKeyInput.focus();
    }
  });

  const closeAuth = () => adminAuthModal.classList.remove("open");
  closeAdminAuthBtn.addEventListener("click", closeAuth);
  cancelAdminAuthBtn.addEventListener("click", closeAuth);

  submitAdminAuthBtn.addEventListener("click", async () => {
    const key = adminKeyInput.value.trim();
    setAdminKey(key);
    const verified = await checkAdminStatus();
    if (verified) {
      closeAuth();
      loadDevices();
    } else {
      adminAuthError.textContent = "Ungültiger Admin API-Key. Bitte prüfe deine Eingabe.";
      adminAuthError.style.display = "block";
    }
  });

  adminKeyInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      submitAdminAuthBtn.click();
    }
  });
}

async function checkAdminStatus() {
  try {
    const res = await fetch("/api/v1/auth/verify", {
      headers: getAuthHeaders()
    });
    if (res.ok) {
      isAdmin = true;
      renderAdminUI();
      return true;
    } else {
      isAdmin = false;
      renderAdminUI();
      return false;
    }
  } catch (e) {
    isAdmin = false;
    renderAdminUI();
    return false;
  }
}

function renderAdminUI() {
  const adminToggleText = document.getElementById("adminToggleText");
  const adminToggleBtn = document.getElementById("adminToggleBtn");
  if (isAdmin) {
    adminToggleBtn.classList.add("btn-primary");
    adminToggleBtn.classList.remove("btn-secondary");
    adminToggleText.innerHTML = "🔓 Admin aktiv (Abmelden)";
  } else {
    adminToggleBtn.classList.remove("btn-primary");
    adminToggleBtn.classList.add("btn-secondary");
    adminToggleText.innerHTML = "🔐 Admin";
  }
}

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
    const data = await safeParseResponse(res);

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
    grid.innerHTML = `<div class="loading-state"><p>❌ Fehler beim Laden der Daten: ${escapeHtml(err.message)}</p></div>`;
  }
}

function createDeviceCard(device) {
  const card = document.createElement("div");
  card.className = "device-card";

  const appPills = (device.applications || []).map(app => `
    <span class="app-pill" title="Mask: ${escapeHtml(app.mask_version || 'N/A')}, ComObjects: ${app.com_objects_count}">
      ⚙️ ${escapeHtml(app.name)} ${app.version ? 'v' + escapeHtml(app.version) : ''}
    </span>
  `).join("");

  const downloadUrl = `/api/v1/download/${encodeURIComponent(device.order_number)}`;
  const hasFile = !!device.knxprod_file;
  const hasSource = hasFile && !!device.knxprod_file.source_url;
  
  let downloadBtn = `<span class="badge">Keine Datei</span>`;
  if (hasFile) {
    downloadBtn = `
      <a href="${downloadUrl}" class="btn btn-primary btn-sm" download>
        ⬇️ .knxprod Download
      </a>
    `;
  }

  const sourceBadge = hasSource ? `
    <a href="${escapeHtml(device.knxprod_file.source_url)}" target="_blank" rel="noopener noreferrer" class="badge-source" title="Offizieller Hersteller-Download-Link">
      🌐 Hersteller-Quelle
    </a>
  ` : '';

  const takedownSubject = encodeURIComponent(`Takedown-Anfrage: KNX-Gerät ${device.order_number}`);
  const takedownBody = encodeURIComponent(`Sehr geehrtes KoNfiX-Team,\n\nals Rechteinhaber bitte ich um Löschung / Sperrung des folgenden Eintrags:\nGerät: ${device.name}\nBestellnummer: ${device.order_number}\n\nBegründung:\n`);
  const takedownLink = `mailto:legal@konfix.sduni.de?subject=${takedownSubject}&body=${takedownBody}`;

  card.innerHTML = `
    <div class="card-top">
      <div>
        <span class="badge badge-mfg">${escapeHtml(device.manufacturer ? device.manufacturer.name : '')}</span>
      </div>
      <span class="order-badge">${escapeHtml(device.order_number)}</span>
    </div>
    
    <h3 class="card-title">${escapeHtml(device.name)}</h3>
    
    <div class="card-specs">
      ${device.hardware_version ? `<span class="spec-item">HW: <strong>v${escapeHtml(device.hardware_version)}</strong></span>` : ''}
      ${device.bus_current_ma != null ? `<span class="spec-item">Bus: <strong>${device.bus_current_ma} mA</strong></span>` : ''}
      ${device.knxprod_file && device.knxprod_file.file_size_bytes ? `<span class="spec-item">Größe: <strong>${formatBytes(device.knxprod_file.file_size_bytes)}</strong></span>` : ''}
      ${sourceBadge}
    </div>

    <div class="app-list">
      ${appPills || '<small style="color: #64748b;">Keine Applikation angegeben</small>'}
    </div>

    <div class="card-actions">
      ${downloadBtn}
    </div>

    <div style="margin-top: 0.5rem; display: flex; justify-content: flex-end;">
      <a href="${takedownLink}" class="btn-text-link" style="color: #64748b; font-size: 0.72rem; text-decoration: underline;">
        🏳️ Rechteinhaber? Takedown anfordern
      </a>
    </div>
  `;

  // REST Details Button
  const restBtn = document.createElement("button");
  restBtn.className = "btn btn-secondary btn-sm";
  restBtn.textContent = "💻 REST Info";
  restBtn.addEventListener("click", () => showRestDetails(device));
  card.querySelector(".card-actions").appendChild(restBtn);

  // Admin Actions (Edit & Delete)
  if (isAdmin) {
    const adminBar = document.createElement("div");
    adminBar.className = "card-admin-actions";
    
    const editBtn = document.createElement("button");
    editBtn.className = "btn btn-sm btn-secondary";
    editBtn.textContent = "✏️ Bearbeiten";
    editBtn.addEventListener("click", () => openEditDeviceModal(device));

    const deleteBtn = document.createElement("button");
    deleteBtn.className = "btn btn-sm btn-danger";
    deleteBtn.textContent = "🗑️ Löschen";
    deleteBtn.addEventListener("click", () => openDeleteDeviceModal(device));

    adminBar.appendChild(editBtn);
    adminBar.appendChild(deleteBtn);
    card.appendChild(adminBar);
  }

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

    <h4 style="font-size: 0.95rem; margin-top: 1.25rem; margin-bottom: 0.35rem; color: #f8fafc;">3. Download mit Hersteller-Redirect (HTTP 302):</h4>
    <div class="code-block">${escapeHtml(`curl -L "${baseUrl}/api/v1/download/${device.order_number}?redirect=true"`)}</div>

    ${device.knxprod_file ? `
      <div style="margin-top: 1.25rem; font-size: 0.8rem; color: #94a3b8;">
        <strong>SHA256 Prüfsumme:</strong><br>
        <code style="color: #38bdf8; font-family: monospace;">${device.knxprod_file.sha256}</code>
        ${device.knxprod_file.source_url ? `
          <div style="margin-top: 0.5rem;">
            <strong>Offizielle Hersteller-Quelle:</strong><br>
            <a href="${escapeHtml(device.knxprod_file.source_url)}" target="_blank" rel="noopener noreferrer" style="color: #38bdf8; word-break: break-all;">
              ${escapeHtml(device.knxprod_file.source_url)}
            </a>
          </div>
        ` : ''}
      </div>
    ` : ''}
  `;

  modal.classList.add("open");
}

function setupUploadTabs() {
  const tabFileBtn = document.getElementById("tabUploadFileBtn");
  const tabUrlBtn = document.getElementById("tabUploadUrlBtn");
  const fileTab = document.getElementById("uploadFileTab");
  const urlTab = document.getElementById("uploadUrlTab");

  tabFileBtn.addEventListener("click", () => {
    tabFileBtn.classList.add("btn-primary");
    tabFileBtn.classList.remove("btn-secondary");
    tabUrlBtn.classList.add("btn-secondary");
    tabUrlBtn.classList.remove("btn-primary");
    fileTab.style.display = "block";
    urlTab.style.display = "none";
  });

  tabUrlBtn.addEventListener("click", () => {
    tabUrlBtn.classList.add("btn-primary");
    tabUrlBtn.classList.remove("btn-secondary");
    tabFileBtn.classList.add("btn-secondary");
    tabFileBtn.classList.remove("btn-primary");
    urlTab.style.display = "block";
    fileTab.style.display = "none";
  });
}

function setupDropZone() {
  const dropZone = document.getElementById("dropZone");
  const fileInput = document.getElementById("fileInput");
  const uploadProgress = document.getElementById("uploadProgress");
  const uploadSpinner = document.getElementById("uploadSpinner");
  const statusText = document.getElementById("uploadStatusText");
  const resultsList = document.getElementById("uploadResultsList");

  dropZone.addEventListener("click", () => {
    const consent = document.getElementById("uploadConsentCheckbox");
    if (consent && !consent.checked) {
      alert("Bitte bestätigen Sie vor der Dateiauswahl das Berechtigungs-Häkchen.");
      return;
    }
    fileInput.click();
  });

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

    const consent = document.getElementById("uploadConsentCheckbox");
    if (consent && !consent.checked) {
      alert("Bitte bestätigen Sie vor dem Upload die rechtliche Berechtigung bzw. die freie Verfügbarkeit der Datei.");
      if (fileInput) fileInput.value = "";
      return;
    }

    const sourceUrlInput = document.getElementById("uploadFileSourceUrl");
    const sourceUrl = sourceUrlInput ? sourceUrlInput.value.trim() : "";

    document.getElementById("uploadFileTab").style.display = "none";
    document.getElementById("uploadUrlTab").style.display = "none";
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
      const formData = new FormData();
      for (const file of files) {
        formData.append("files", file);
      }

      const headers = getAuthHeaders();
      let uploadEndpoint = "/api/v1/upload/batch";
      if (sourceUrl) {
        uploadEndpoint += `?source_url=${encodeURIComponent(sourceUrl)}`;
      }

      const res = await fetch(uploadEndpoint, {
        method: "POST",
        headers: headers,
        body: formData
      });

      const data = await safeParseResponse(res);
      if (uploadSpinner) uploadSpinner.style.display = "none";

      if (data.results) {
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
      }, data.results && data.results.length > 3 ? 3500 : 2000);

    } catch (err) {
      if (uploadSpinner) uploadSpinner.style.display = "none";
      statusText.innerHTML = `
        <span style="color: #ef4444; font-weight: 600;">❌ Fehler:</span><br>
        ${escapeHtml(err.message)}<br><br>
      `;
      const retryBtn = document.createElement("button");
      retryBtn.className = "btn btn-secondary btn-sm";
      retryBtn.textContent = "Erneut versuchen";
      retryBtn.addEventListener("click", resetUploadUI);
      statusText.appendChild(retryBtn);
    }
  }
}

function setupUrlImport() {
  const startBtn = document.getElementById("startUrlImportBtn");
  const urlInput = document.getElementById("urlImportInput");
  const storeBinaryCheckbox = document.getElementById("urlImportStoreBinary");
  const consentCheckbox = document.getElementById("urlConsentCheckbox");
  const uploadProgress = document.getElementById("uploadProgress");
  const uploadSpinner = document.getElementById("uploadSpinner");
  const statusText = document.getElementById("uploadStatusText");

  startBtn.addEventListener("click", async () => {
    const url = urlInput.value.trim();
    if (!url) {
      alert("Bitte gib eine gültige Hersteller-URL ein.");
      urlInput.focus();
      return;
    }
    if (!consentCheckbox.checked) {
      alert("Bitte bestätige das Häkchen für die freie Verfügbarkeit des Hersteller-Links.");
      return;
    }

    document.getElementById("uploadFileTab").style.display = "none";
    document.getElementById("uploadUrlTab").style.display = "none";
    uploadProgress.style.display = "block";
    if (uploadSpinner) uploadSpinner.style.display = "block";
    statusText.textContent = `Lade Datei von ${url} herunter und indexiere Metadaten...`;

    try {
      const res = await fetch("/api/v1/upload/url", {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          url: url,
          store_binary: storeBinaryCheckbox.checked
        })
      });

      const data = await safeParseResponse(res);
      if (uploadSpinner) uploadSpinner.style.display = "none";

      statusText.innerHTML = `
        <span style="color: #10b981; font-weight: 600;">✓ Erfolgreich von Hersteller-Link indexiert!</span><br>
        Hersteller: <strong>${escapeHtml(data.manufacturer_name)}</strong><br>
        Geräte: ${data.devices_imported.map(d => `<code>${escapeHtml(d.order_number)}</code>`).join(", ")}<br>
        <small style="color: #94a3b8;">${storeBinaryCheckbox.checked ? "Datei wurde lokal gecacht." : "100% rechtssicher: Reines Metadaten-Indexing & Verlinkung."}</small>
      `;

      setTimeout(() => {
        document.getElementById("uploadModal").classList.remove("open");
        resetUploadUI();
        loadStats();
        loadManufacturers();
        loadDevices();
      }, 2500);

    } catch (err) {
      if (uploadSpinner) uploadSpinner.style.display = "none";
      statusText.innerHTML = `
        <span style="color: #ef4444; font-weight: 600;">❌ Fehler beim Import von URL:</span><br>
        ${escapeHtml(err.message)}<br><br>
      `;
      const retryBtn = document.createElement("button");
      retryBtn.className = "btn btn-secondary btn-sm";
      retryBtn.textContent = "Erneut versuchen";
      retryBtn.addEventListener("click", resetUploadUI);
      statusText.appendChild(retryBtn);
    }
  });
}

function resetUploadUI() {
  document.getElementById("uploadFileTab").style.display = "block";
  document.getElementById("uploadUrlTab").style.display = "none";
  document.getElementById("uploadProgress").style.display = "none";

  const tabFileBtn = document.getElementById("tabUploadFileBtn");
  const tabUrlBtn = document.getElementById("tabUploadUrlBtn");
  if (tabFileBtn && tabUrlBtn) {
    tabFileBtn.classList.add("btn-primary");
    tabFileBtn.classList.remove("btn-secondary");
    tabUrlBtn.classList.add("btn-secondary");
    tabUrlBtn.classList.remove("btn-primary");
  }

  const spinner = document.getElementById("uploadSpinner");
  if (spinner) spinner.style.display = "block";
  const resultsList = document.getElementById("uploadResultsList");
  if (resultsList) {
    resultsList.style.display = "none";
    resultsList.innerHTML = "";
  }
  const fileInput = document.getElementById("fileInput");
  if (fileInput) fileInput.value = "";
  const sourceUrlInput = document.getElementById("uploadFileSourceUrl");
  if (sourceUrlInput) sourceUrlInput.value = "";
  const consent1 = document.getElementById("uploadConsentCheckbox");
  if (consent1) consent1.checked = false;
  const consent2 = document.getElementById("urlConsentCheckbox");
  if (consent2) consent2.checked = false;
  const urlInput = document.getElementById("urlImportInput");
  if (urlInput) urlInput.value = "";
}

// Edit Device Modal Logic
function setupEditModal() {
  const modal = document.getElementById("editDeviceModal");
  const closeBtn = document.getElementById("closeEditDeviceBtn");
  const cancelBtn = document.getElementById("cancelEditDeviceBtn");
  const saveBtn = document.getElementById("saveEditDeviceBtn");
  const statusDiv = document.getElementById("editDeviceStatus");

  const closeModal = () => modal.classList.remove("open");
  closeBtn.addEventListener("click", closeModal);
  cancelBtn.addEventListener("click", closeModal);

  saveBtn.addEventListener("click", async () => {
    const orderNumber = document.getElementById("editOrderNumber").value;
    const name = document.getElementById("editDeviceName").value.trim();
    const sourceUrl = document.getElementById("editSourceUrl").value.trim();
    const hwVersion = document.getElementById("editHardwareVersion").value.trim();
    const busCurrentStr = document.getElementById("editBusCurrent").value.trim();
    const description = document.getElementById("editDescription").value.trim();

    const payload = {
      name: name,
      source_url: sourceUrl || null,
      hardware_version: hwVersion || null,
      bus_current_ma: busCurrentStr ? parseFloat(busCurrentStr) : null,
      description: description || null
    };

    saveBtn.disabled = true;
    saveBtn.textContent = "Speichere...";
    statusDiv.style.display = "none";

    try {
      const res = await fetch(`/api/v1/devices/${encodeURIComponent(orderNumber)}`, {
        method: "PATCH",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(payload)
      });

      await safeParseResponse(res);
      statusDiv.innerHTML = `<span style="color: #10b981; font-weight: 600;">✓ Gerät erfolgreich aktualisiert!</span>`;
      statusDiv.style.display = "block";

      setTimeout(() => {
        closeModal();
        saveBtn.disabled = false;
        saveBtn.textContent = "Änderungen speichern";
        loadDevices();
      }, 1000);

    } catch (err) {
      saveBtn.disabled = false;
      saveBtn.textContent = "Änderungen speichern";
      statusDiv.innerHTML = `<span style="color: #ef4444; font-weight: 600;">❌ Fehler: ${escapeHtml(err.message)}</span>`;
      statusDiv.style.display = "block";
    }
  });
}

function openEditDeviceModal(device) {
  const modal = document.getElementById("editDeviceModal");
  document.getElementById("editOrderNumber").value = device.order_number;
  document.getElementById("editOrderNumberDisplay").value = device.order_number;
  document.getElementById("editDeviceName").value = device.name || "";
  document.getElementById("editSourceUrl").value = (device.knxprod_file && device.knxprod_file.source_url) || "";
  document.getElementById("editHardwareVersion").value = device.hardware_version || "";
  document.getElementById("editBusCurrent").value = device.bus_current_ma != null ? device.bus_current_ma : "";
  document.getElementById("editDescription").value = device.description || "";
  document.getElementById("editDeviceStatus").style.display = "none";

  modal.classList.add("open");
}

// Delete Device Modal Logic
function setupDeleteModal() {
  const modal = document.getElementById("deleteDeviceModal");
  const closeBtn = document.getElementById("closeDeleteDeviceBtn");
  const cancelBtn = document.getElementById("cancelDeleteDeviceBtn");
  const confirmBtn = document.getElementById("confirmDeleteDeviceBtn");
  const statusDiv = document.getElementById("deleteDeviceStatus");

  const closeModal = () => modal.classList.remove("open");
  closeBtn.addEventListener("click", closeModal);
  cancelBtn.addEventListener("click", closeModal);

  confirmBtn.addEventListener("click", async () => {
    if (!currentDeleteOrderNumber) return;

    const deleteFile = document.getElementById("deleteFileCheckbox").checked;
    confirmBtn.disabled = true;
    confirmBtn.textContent = "Lösche...";
    statusDiv.style.display = "none";

    try {
      const res = await fetch(`/api/v1/devices/${encodeURIComponent(currentDeleteOrderNumber)}?delete_file=${deleteFile}`, {
        method: "DELETE",
        headers: getAuthHeaders()
      });

      await safeParseResponse(res);
      statusDiv.innerHTML = `<span style="color: #10b981; font-weight: 600;">✓ Gerät erfolgreich gelöscht!</span>`;
      statusDiv.style.display = "block";

      setTimeout(() => {
        closeModal();
        confirmBtn.disabled = false;
        confirmBtn.textContent = "Endgültig löschen";
        loadStats();
        loadManufacturers();
        loadDevices();
      }, 1000);

    } catch (err) {
      confirmBtn.disabled = false;
      confirmBtn.textContent = "Endgültig löschen";
      statusDiv.innerHTML = `<span style="color: #ef4444; font-weight: 600;">❌ Fehler: ${escapeHtml(err.message)}</span>`;
      statusDiv.style.display = "block";
    }
  });
}

function openDeleteDeviceModal(device) {
  currentDeleteOrderNumber = device.order_number;
  const modal = document.getElementById("deleteDeviceModal");
  document.getElementById("deleteDeviceDesc").innerHTML = `
    Möchtest du das Gerät <strong>${escapeHtml(device.name)}</strong> (<code>${escapeHtml(device.order_number)}</code>) wirklich dauerhaft aus dem Katalog entfernen?
  `;
  document.getElementById("deleteDeviceStatus").style.display = "none";
  modal.classList.add("open");
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

async function safeParseResponse(res) {
  let text = "";
  try {
    text = await res.text();
  } catch (err) {
    throw new Error(`Konnte Server-Antwort nicht lesen: ${err.message}`);
  }

  let data = null;
  if (text && text.trim().length > 0) {
    try {
      data = JSON.parse(text);
    } catch (err) {
      data = null;
    }
  }

  if (!res.ok) {
    let errorMsg = `Server-Fehler: HTTP ${res.status} (${res.statusText || "Fehler"})`;
    if (data && (data.detail || data.message)) {
      errorMsg = data.detail || data.message;
    } else if (text && text.length < 300 && !text.includes("<html") && !text.includes("<!DOCTYPE")) {
      errorMsg = text.trim();
    }
    throw new Error(errorMsg);
  }

  if (!data) {
    throw new Error(`Unerwartete leere Antwort vom Server (HTTP ${res.status})`);
  }

  return data;
}
