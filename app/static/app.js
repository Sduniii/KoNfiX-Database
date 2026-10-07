// KoNfiX-Catalog Frontend Logic

let allManufacturers = [];
let searchTimeout = null;
let isAdmin = false;
let currentDeleteOrderNumber = null;
const selectedDevices = new Map(); // order_number -> device_name

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
  setupBatchDeleteModal();
  setupYamlModal();
  setupEditorModal();
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
    selectedDevices.clear();
  }
  updateBulkToolbar();
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

  const isSelected = selectedDevices.has(device.order_number);
  if (isSelected) {
    card.classList.add("selected");
  }

  const appPills = (device.applications || []).map(app => `
    <span class="app-pill" title="Mask: ${escapeHtml(app.mask_version || 'N/A')}, ComObjects: ${app.com_objects_count}">
      ⚙️ ${escapeHtml(app.name)} ${app.version ? 'v' + escapeHtml(app.version) : ''}
    </span>
  `).join("");

  const yamlUrl = `/api/v1/devices/yaml?order_number=${encodeURIComponent(device.order_number)}`;
  const sourceUrl = device.source_url || (device.knxprod_file && device.knxprod_file.source_url);
  const hasSource = !!sourceUrl;
  
  const actionButtons = `
    <button type="button" class="btn btn-secondary btn-sm btn-view-yaml" data-order="${escapeHtml(device.order_number)}" data-name="${escapeHtml(device.name)}">
      📄 YAML ansehen
    </button>
    <a href="${yamlUrl}" class="btn btn-primary btn-sm" download="${escapeHtml(device.order_number)}.yaml" title="KoNfiX-YAML Gerätedefinition herunterladen">
      ⬇️ .yaml
    </a>
  `;

  const sourceBadge = hasSource ? `
    <a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer" class="badge-source" title="Offizieller Hersteller-Download-Link">
      🌐 Hersteller-Quelle
    </a>
  ` : '';

  const takedownSubject = encodeURIComponent(`Takedown-Anfrage: KNX-Gerät ${device.order_number}`);
  const takedownBody = encodeURIComponent(`Sehr geehrtes KoNfiX-Team,\n\nals Rechteinhaber bitte ich um Löschung / Sperrung des folgenden Eintrags:\nGerät: ${device.name}\nBestellnummer: ${device.order_number}\n\nBegründung:\n`);
  const takedownLink = `mailto:legal@konfix.sduni.de?subject=${takedownSubject}&body=${takedownBody}`;

  const mfgName = device.manufacturer ? device.manufacturer.name : '';
  const mfgCode = device.manufacturer && device.manufacturer.code ? ` (@${device.manufacturer.code})` : '';
  const mfgBadgeText = escapeHtml(mfgName + mfgCode);

  const leftHeader = isAdmin ? `
    <div style="display: flex; align-items: center; gap: 0.5rem;">
      <input type="checkbox" class="device-select-checkbox" data-order="${escapeHtml(device.order_number)}" data-name="${escapeHtml(device.name)}" ${isSelected ? 'checked' : ''} title="Auswählen für Sammelaktion">
      <span class="badge badge-mfg">${mfgBadgeText}</span>
    </div>
  ` : `
    <div>
      <span class="badge badge-mfg">${mfgBadgeText}</span>
    </div>
  `;

  const rightHeader = isAdmin ? `
    <div style="display: flex; align-items: center; gap: 0.35rem;">
      <span class="order-badge">${escapeHtml(device.order_number)}</span>
      <div class="card-admin-group">
        <button type="button" class="admin-icon-btn btn-edit" title="Gerät bearbeiten" aria-label="Bearbeiten">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
          </svg>
        </button>
        <button type="button" class="admin-icon-btn btn-delete" title="Gerät löschen" aria-label="Löschen">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            <line x1="10" y1="11" x2="10" y2="17"></line>
            <line x1="14" y1="11" x2="14" y2="17"></line>
          </svg>
        </button>
      </div>
    </div>
  ` : `
    <span class="order-badge">${escapeHtml(device.order_number)}</span>
  `;

  card.innerHTML = `
    <div class="card-top">
      ${leftHeader}
      ${rightHeader}
    </div>
    
    <h3 class="card-title">${escapeHtml(device.name)}</h3>
    
    <div class="card-specs">
      ${device.hardware_version ? `<span class="spec-item">HW: <strong>v${escapeHtml(device.hardware_version)}</strong></span>` : ''}
      ${device.bus_current_ma != null ? `<span class="spec-item">Bus: <strong>${device.bus_current_ma} mA</strong></span>` : ''}
      ${sourceBadge}
    </div>

    <div class="app-list">
      ${appPills || '<small style="color: #64748b;">Keine Applikation angegeben</small>'}
    </div>

    <div class="card-actions">
      ${actionButtons}
    </div>

    <div style="margin-top: 0.5rem; display: flex; justify-content: flex-end;">
      <a href="${takedownLink}" class="btn-text-link" style="color: #64748b; font-size: 0.72rem; text-decoration: underline;">
        🏳️ Rechteinhaber? Takedown anfordern
      </a>
    </div>
  `;

  // Wire up YAML Viewer Button
  const viewYamlBtn = card.querySelector(".btn-view-yaml");
  if (viewYamlBtn) {
    viewYamlBtn.addEventListener("click", () => {
      openYamlViewer(device.order_number, device.name);
    });
  }

  // REST Details Button
  const restBtn = document.createElement("button");
  restBtn.className = "btn btn-secondary btn-sm";
  restBtn.textContent = "💻 REST Info";
  restBtn.addEventListener("click", () => showRestDetails(device));
  card.querySelector(".card-actions").appendChild(restBtn);

  // Open in Sandbox Editor Button
  const editSandboxBtn = document.createElement("button");
  editSandboxBtn.className = "btn btn-secondary btn-sm";
  editSandboxBtn.textContent = "🛠️ Im Editor öffnen";
  editSandboxBtn.title = "Im lokalen KoNfiX-YAML Editor bearbeiten";
  editSandboxBtn.addEventListener("click", () => {
    openDeviceInSandbox(device.order_number);
  });
  card.querySelector(".card-actions").appendChild(editSandboxBtn);


  // Admin Event Listeners
  if (isAdmin) {
    const editBtn = card.querySelector(".btn-edit");
    if (editBtn) {
      editBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        openEditDeviceModal(device);
      });
    }

    const deleteBtn = card.querySelector(".btn-delete");
    if (deleteBtn) {
      deleteBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        openDeleteDeviceModal(device);
      });
    }

    const checkbox = card.querySelector(".device-select-checkbox");
    if (checkbox) {
      checkbox.addEventListener("change", (e) => {
        e.stopPropagation();
        toggleDeviceSelection(device.order_number, device.name, checkbox.checked, card);
      });
    }
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
  --output "${device.order_number}.yaml"`;

  const getCurl = `curl -L -O "${baseUrl}/api/v1/download/${device.order_number}"`;

  title.textContent = `${device.name} (${device.order_number})`;

  const modalSourceUrl = device.source_url || (device.knxprod_file && device.knxprod_file.source_url);

  body.innerHTML = `
    <p style="margin-bottom: 1rem; color: #94a3b8;">
      Diese KoNfiX-Gerätedefinition kann direkt per REST-API automatisiert in Skripte oder CI/CD-Pipelines eingebunden werden.
    </p>

    <h4 style="font-size: 0.95rem; margin-bottom: 0.35rem; color: #f8fafc;">1. Download per POST (YAML):</h4>
    <div class="code-block">${escapeHtml(postCurl)}</div>

    <h4 style="font-size: 0.95rem; margin-top: 1.25rem; margin-bottom: 0.35rem; color: #f8fafc;">2. Download per GET (YAML):</h4>
    <div class="code-block">${escapeHtml(getCurl)}</div>

    ${modalSourceUrl ? `
      <h4 style="font-size: 0.95rem; margin-top: 1.25rem; margin-bottom: 0.35rem; color: #f8fafc;">3. Download mit Hersteller-Redirect (HTTP 302):</h4>
      <div class="code-block">${escapeHtml(`curl -L "${baseUrl}/api/v1/download/${device.order_number}?redirect=true"`)}</div>

      <div style="margin-top: 1.25rem; font-size: 0.8rem; color: #94a3b8;">
        <div>
          <strong>Offizielle Hersteller-Quelle:</strong><br>
          <a href="${escapeHtml(modalSourceUrl)}" target="_blank" rel="noopener noreferrer" style="color: #38bdf8; word-break: break-all;">
            ${escapeHtml(modalSourceUrl)}
          </a>
        </div>
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

  function appendResultItem(item) {
    if (!resultsList) return;
    resultsList.style.display = "block";
    const itemSuccess = item.status === "success";
    const badgeClass = itemSuccess ? "success" : "error";
    const badgeText = itemSuccess ? "OK" : "Fehler";
    const devCount = item.devices_imported ? item.devices_imported.length : 0;
    const detail = itemSuccess
      ? `${devCount} Gerät(e) indexiert`
      : escapeHtml(item.message || "Fehler beim Import");

    const row = document.createElement("div");
    row.className = "upload-result-item";
    row.innerHTML = `
      <div>
        <div class="item-name" title="${escapeHtml(item.filename)}">${escapeHtml(item.filename)}</div>
        <small style="color: #64748b; font-size: 0.72rem;">${detail}</small>
      </div>
      <span class="item-badge ${badgeClass}">${badgeText}</span>
    `;
    resultsList.appendChild(row);
  }

  function uploadSingleFile(file, sourceUrl, headers, onProgress, onStatus) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      let uploadEndpoint = "/api/v1/upload/batch";
      if (sourceUrl) {
        uploadEndpoint += `?source_url=${encodeURIComponent(sourceUrl)}`;
      }
      xhr.open("POST", uploadEndpoint);
      for (const [key, value] of Object.entries(headers)) {
        xhr.setRequestHeader(key, value);
      }

      const formData = new FormData();
      formData.append("files", file);

      let convTimer = null;
      let convProgress = 50;

      xhr.upload.onprogress = (evt) => {
        if (evt.lengthComputable) {
          const uploadPct = Math.round((evt.loaded / evt.total) * 50);
          onProgress(uploadPct);
          onStatus(`Übertrage '${file.name}' (${Math.round((evt.loaded / evt.total) * 100)}%)...`);
        }
      };

      xhr.upload.onload = () => {
        onProgress(50);
        onStatus(`⚡ Konvertiere XML-Metadaten & erzeuge KoNfiX-YAML...`);
        convTimer = setInterval(() => {
          if (convProgress < 95) {
            convProgress += Math.max(1, Math.round((95 - convProgress) * 0.1));
            onProgress(convProgress);
          }
        }, 250);
      };

      xhr.onload = () => {
        if (convTimer) clearInterval(convTimer);
        let resJson;
        try {
          resJson = JSON.parse(xhr.responseText);
        } catch (_) {
          return reject(new Error(`Server-Fehler: Ungültige Antwort (HTTP ${xhr.status})`));
        }

        if (xhr.status >= 200 && xhr.status < 300) {
          onProgress(100);
          resolve(resJson);
        } else {
          reject(new Error(resJson.detail || resJson.message || `HTTP ${xhr.status}`));
        }
      };

      xhr.onerror = () => {
        if (convTimer) clearInterval(convTimer);
        reject(new Error(`Netzwerkfehler während des Uploads von '${file.name}'`));
      };

      xhr.send(formData);
    });
  }

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

    const progressBar = document.getElementById("uploadProgressBar");
    const percentBadge = document.getElementById("uploadPercentBadge");
    if (progressBar) {
      progressBar.style.width = "0%";
      progressBar.style.background = "";
      progressBar.classList.add("converting");
    }
    if (percentBadge) percentBadge.textContent = "0%";

    const fileCount = files.length;
    const headers = getAuthHeaders();
    const allResults = [];
    let successFiles = 0;
    let failedFiles = 0;

    for (let i = 0; i < fileCount; i++) {
      const file = files[i];
      const basePct = (i / fileCount) * 100;
      const sliceWidth = 100 / fileCount;

      const setGlobalPct = (subPct) => {
        const isFinal = (i === fileCount - 1 && subPct >= 100);
        const globalPct = isFinal ? 100 : Math.min(99, Math.round(basePct + (subPct / 100) * sliceWidth));
        if (progressBar) progressBar.style.width = globalPct + "%";
        if (percentBadge) percentBadge.textContent = globalPct + "%";
      };

      try {
        const fileData = await uploadSingleFile(
          file,
          sourceUrl,
          headers,
          (subPct) => setGlobalPct(subPct),
          (subStatus) => {
            statusText.textContent = fileCount === 1
              ? subStatus
              : `[${i + 1}/${fileCount}] ${subStatus}`;
          }
        );

        if (fileData.results && fileData.results.length > 0) {
          for (const item of fileData.results) {
            allResults.push(item);
            if (item.status === "success") successFiles++;
            else failedFiles++;
            appendResultItem(item);
          }
        } else if (fileData.devices_imported) {
          const item = {
            filename: file.name,
            status: "success",
            devices_imported: fileData.devices_imported,
            message: fileData.message || `${fileData.devices_imported.length} Geräte indexiert`
          };
          allResults.push(item);
          successFiles++;
          appendResultItem(item);
        }
      } catch (err) {
        failedFiles++;
        const errItem = {
          filename: file.name,
          status: "error",
          message: err.message
        };
        allResults.push(errItem);
        appendResultItem(errItem);
      }
    }

    if (progressBar) {
      progressBar.classList.remove("converting");
      progressBar.style.width = "100%";
    }
    if (percentBadge) percentBadge.textContent = "100%";
    if (uploadSpinner) uploadSpinner.style.display = "none";

    const isAllSuccess = failedFiles === 0 && successFiles > 0;
    const isPartial = failedFiles > 0 && successFiles > 0;
    const statusColor = isAllSuccess ? "#10b981" : (isPartial ? "#f59e0b" : "#ef4444");
    const statusIcon = isAllSuccess ? "✓" : (isPartial ? "⚠️" : "❌");

    statusText.innerHTML = `
      <span style="color: ${statusColor}; font-weight: 600;">
        ${statusIcon} Import abgeschlossen: ${successFiles} erfolgreich, ${failedFiles} Fehler
      </span>
    `;

    setTimeout(() => {
      document.getElementById("uploadModal").classList.remove("open");
      resetUploadUI();
      loadStats();
      loadManufacturers();
      loadDevices();
    }, allResults.length > 3 ? 4000 : 2500);
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
  const pb = document.getElementById("uploadProgressBar");
  if (pb) {
    pb.style.width = "0%";
    pb.style.background = "linear-gradient(90deg, #38bdf8, #818cf8)";
  }
  const badge = document.getElementById("uploadPercentBadge");
  if (badge) badge.textContent = "0%";
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
  document.getElementById("editSourceUrl").value = device.source_url || (device.knxprod_file && device.knxprod_file.source_url) || "";
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

// Bulk Selection and Batch Delete Handling
function toggleDeviceSelection(orderNumber, deviceName, isSelected, cardElement) {
  if (isSelected) {
    selectedDevices.set(orderNumber, deviceName);
    if (cardElement) cardElement.classList.add("selected");
  } else {
    selectedDevices.delete(orderNumber);
    if (cardElement) cardElement.classList.remove("selected");
  }
  updateBulkToolbar();
}

function updateBulkToolbar() {
  const toolbar = document.getElementById("bulkActionsToolbar");
  const countBadge = document.getElementById("bulkSelectedCount");
  const countText = document.getElementById("bulkSelectedText");
  if (!toolbar || !countBadge || !countText) return;

  const count = selectedDevices.size;
  countBadge.textContent = count;
  countText.textContent = count === 1 ? "Gerät ausgewählt" : "Geräte ausgewählt";

  if (isAdmin && count > 0) {
    toolbar.style.display = "block";
  } else {
    toolbar.style.display = "none";
  }
}

function setupBatchDeleteModal() {
  const modal = document.getElementById("batchDeleteModal");
  const closeBtn = document.getElementById("closeBatchDeleteBtn");
  const cancelBtn = document.getElementById("cancelBatchDeleteBtn");
  const confirmBtn = document.getElementById("confirmBatchDeleteBtn");
  const statusDiv = document.getElementById("batchDeleteStatus");
  const listDiv = document.getElementById("batchDeleteList");
  const descP = document.getElementById("batchDeleteDesc");
  const filesCheckbox = document.getElementById("batchDeleteFilesCheckbox");

  const bulkSelectAllBtn = document.getElementById("bulkSelectAllBtn");
  const bulkDeselectAllBtn = document.getElementById("bulkDeselectAllBtn");
  const bulkDeleteBtn = document.getElementById("bulkDeleteBtn");

  if (bulkSelectAllBtn) {
    bulkSelectAllBtn.addEventListener("click", () => {
      document.querySelectorAll(".device-card").forEach(c => {
        const cb = c.querySelector(".device-select-checkbox");
        if (cb) {
          cb.checked = true;
          c.classList.add("selected");
          selectedDevices.set(cb.dataset.order, cb.dataset.name || cb.dataset.order);
        }
      });
      updateBulkToolbar();
    });
  }

  if (bulkDeselectAllBtn) {
    bulkDeselectAllBtn.addEventListener("click", () => {
      selectedDevices.clear();
      document.querySelectorAll(".device-card").forEach(c => {
        const cb = c.querySelector(".device-select-checkbox");
        if (cb) cb.checked = false;
        c.classList.remove("selected");
      });
      updateBulkToolbar();
    });
  }

  if (bulkDeleteBtn) {
    bulkDeleteBtn.addEventListener("click", () => {
      if (selectedDevices.size === 0) return;

      descP.innerHTML = `Möchtest du die folgenden <strong>${selectedDevices.size}</strong> ausgewählten Geräte wirklich unwiderruflich aus dem Katalog entfernen?`;
      listDiv.innerHTML = "";
      selectedDevices.forEach((name, order) => {
        const item = document.createElement("div");
        item.className = "batch-delete-item";
        item.innerHTML = `<strong>${escapeHtml(order)}</strong> <span style="color: #94a3b8;">${escapeHtml(name)}</span>`;
        listDiv.appendChild(item);
      });

      statusDiv.style.display = "none";
      modal.classList.add("open");
    });
  }

  const closeModal = () => modal.classList.remove("open");
  if (closeBtn) closeBtn.addEventListener("click", closeModal);
  if (cancelBtn) cancelBtn.addEventListener("click", closeModal);

  if (confirmBtn) {
    confirmBtn.addEventListener("click", async () => {
      const orderNumbers = Array.from(selectedDevices.keys());
      if (orderNumbers.length === 0) return;

      confirmBtn.disabled = true;
      confirmBtn.textContent = "Lösche...";
      statusDiv.style.display = "none";

      try {
        const res = await fetch("/api/v1/devices/batch-delete", {
          method: "POST",
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({
            order_numbers: orderNumbers,
            delete_files: filesCheckbox.checked
          })
        });

        const data = await safeParseResponse(res);
        statusDiv.innerHTML = `<span style="color: #10b981; font-weight: 600;">✓ ${escapeHtml(data.message)}</span>`;
        statusDiv.style.display = "block";

        selectedDevices.clear();
        updateBulkToolbar();

        setTimeout(() => {
          closeModal();
          confirmBtn.disabled = false;
          confirmBtn.textContent = "Ausgewählte endgültig löschen";
          loadStats();
          loadManufacturers();
          loadDevices();
        }, 1000);

      } catch (err) {
        confirmBtn.disabled = false;
        confirmBtn.textContent = "Ausgewählte endgültig löschen";
        statusDiv.innerHTML = `<span style="color: #ef4444; font-weight: 600;">❌ Fehler: ${escapeHtml(err.message)}</span>`;
        statusDiv.style.display = "block";
      }
    });
  }
}

// YAML Viewer Modal Logic
function setupYamlModal() {
  const yamlModal = document.getElementById("yamlModal");
  const closeYamlBtn = document.getElementById("closeYamlBtn");
  const copyYamlBtn = document.getElementById("copyYamlBtn");

  if (closeYamlBtn) {
    closeYamlBtn.addEventListener("click", () => yamlModal.classList.remove("open"));
  }

  if (copyYamlBtn) {
    copyYamlBtn.addEventListener("click", async () => {
      const code = document.getElementById("yamlContentPre").textContent;
      try {
        await navigator.clipboard.writeText(code);
        const originalText = copyYamlBtn.textContent;
        copyYamlBtn.textContent = "✅ Kopiert!";
        setTimeout(() => {
          copyYamlBtn.textContent = originalText;
        }, 2000);
      } catch (err) {
        alert("Fehler beim Kopieren in die Zwischenablage");
      }
    });
  }
}

async function openYamlViewer(orderNumber, deviceName) {
  const yamlModal = document.getElementById("yamlModal");
  const title = document.getElementById("yamlModalTitle");
  const subtitle = document.getElementById("yamlModalSubtitle");
  const pre = document.getElementById("yamlContentPre");
  const dlBtn = document.getElementById("downloadYamlModalBtn");

  title.textContent = `📄 ${deviceName || orderNumber}`;
  subtitle.textContent = `KoNfiX-YAML: ${orderNumber}`;
  pre.innerHTML = `<code>Lade YAML-Definition...</code>`;
  const yamlUrl = `/api/v1/devices/yaml?order_number=${encodeURIComponent(orderNumber)}`;
  dlBtn.href = yamlUrl;
  dlBtn.setAttribute("download", `${orderNumber}.yaml`);

  yamlModal.classList.add("open");

  try {
    const res = await fetch(yamlUrl);
    if (!res.ok) {
      let errDetail = "Fehler beim Laden der YAML-Definition.";
      try {
        const errJson = await res.json();
        if (errJson && errJson.detail) errDetail = errJson.detail;
      } catch (_) {}
      pre.textContent = errDetail;
      return;
    }
    const yamlText = await res.text();
    pre.textContent = yamlText;
  } catch (err) {
    pre.textContent = `Netzwerkfehler: ${err.message}`;
  }
}

// ==========================================
// Standalone KoNfiX-YAML Editor (Sandbox)
// ==========================================

const EDITOR_TEMPLATES = {
  switch: `$schema: https://konfix.sduni.de/schemas/konfix-device-v1.json
konfix_version: '1.0'
manufacturer:
  code: openknx
  name: OpenKNX Community
device:
  order_number: OFM-SA-0416
  name: Schaltaktor 4-fach 16A
  description: 4-fach KNX Schaltaktor mit Relaisüberwachung und Treppenlichtfunktion
  hardware:
    name: OFM-SA4
    version: '1.0'
    bus_current_ma: 10.0
application:
  id: openknx_sa-0416_v1
  name: Schalten 4f 16A
  version: '1.0'
  mask_version: MV-07B0
communication_objects:
  - id: openknx_o-1
    number: 1
    name: Kanal A Schalten
    function: Ein/Aus
    dpt: 1.001
    size: 1 Bit
    flags:
      communication: true
      read: false
      write: true
      transmit: false
      update: false
  - id: openknx_o-2
    number: 2
    name: Kanal A Status
    function: Rückmeldung
    dpt: 1.001
    size: 1 Bit
    flags:
      communication: true
      read: true
      write: false
      transmit: true
      update: false
  - id: openknx_o-3
    number: 3
    name: Kanal B Schalten
    function: Ein/Aus
    dpt: 1.001
    size: 1 Bit
    flags:
      communication: true
      read: false
      write: true
      transmit: false
      update: false
  - id: openknx_o-4
    number: 4
    name: Kanal B Status
    function: Rückmeldung
    dpt: 1.001
    size: 1 Bit
    flags:
      communication: true
      read: true
      write: false
      transmit: true
      update: false
parameters:
  - id: openknx_p-1
    name: Betriebsart Kanal A
    text: Betriebsart Kanal A
    type: enum
    default: '1'
    options:
      - value: '1'
        text: Schließer
      - value: '2'
        text: Öffner
      - value: '3'
        text: Treppenlicht
    page: Kanal A > Allgemein
  - id: openknx_p-2
    name: Treppenlichtzeit (Sekunden)
    text: Treppenlichtzeit
    type: number
    default: 180
    page: Kanal A > Zeitfunktionen
    section: Treppenlicht
    conditions:
      - param_id: openknx_p-1
        when_values:
          - '3'
`,
  dimmer: `$schema: https://konfix.sduni.de/schemas/konfix-device-v1.json
konfix_version: '1.0'
manufacturer:
  code: mdt
  name: MDT technologies
device:
  order_number: AKD-0201.02
  name: Dimmaktor 2-fach 250W
  description: Universeller Dimmaktor für Phasenanschnitt und Phasenabschnitt
  hardware:
    name: AKD-0201
    version: '2.0'
    bus_current_ma: 12.0
application:
  id: mdt_akd-0201_v2
  name: Dimmen 2f 250W
  version: '2.0'
  mask_version: MV-07B0
communication_objects:
  - id: mdt_o-1
    number: 1
    name: Kanal A Schalten
    function: Ein/Aus
    dpt: 1.001
    size: 1 Bit
    flags: { communication: true, read: false, write: true, transmit: false, update: false }
  - id: mdt_o-2
    number: 2
    name: Kanal A Dimmen relativ
    function: Heller/Dunkler
    dpt: 3.007
    size: 4 Bit
    flags: { communication: true, read: false, write: true, transmit: false, update: false }
  - id: mdt_o-3
    number: 3
    name: Kanal A Dimmwert
    function: Helligkeitswert
    dpt: 5.001
    size: 1 Byte
    flags: { communication: true, read: false, write: true, transmit: false, update: false }
  - id: mdt_o-4
    number: 4
    name: Kanal A Status Dimmwert
    function: Rückmeldung Helligkeit
    dpt: 5.001
    size: 1 Byte
    flags: { communication: true, read: true, write: false, transmit: true, update: false }
parameters:
  - id: mdt_p-1
    name: Lastart Kanal A
    text: Lastart Kanal A
    type: enum
    default: 'auto'
    options:
      - { value: 'auto', text: Automatische Lasterkennung }
      - { value: 'trailing', text: Phasenabschnitt (LED) }
      - { value: 'leading', text: Phasenanschnitt }
    page: Kanal A > Dimmkurve
  - id: mdt_p-2
    name: Einschaltzeit Dimmwert (Sekunden)
    text: Einschaltzeit Dimmwert
    type: number
    default: 2.0
    page: Kanal A > Dimmkurve
`,
  shutter: `$schema: https://konfix.sduni.de/schemas/konfix-device-v1.json
konfix_version: '1.0'
manufacturer:
  code: mdt
  name: MDT technologies
device:
  order_number: JAL-0410.02
  name: Jalousieaktor 4-fach 10A
  description: 4-fach Jalousie-/Rollladenaktor mit automatischer Fahrzeitermittlung
  hardware:
    name: JAL-0410
    version: '2.0'
    bus_current_ma: 10.0
application:
  id: mdt_jal-0410_v2
  name: Jalousie 4f 10A
  version: '2.0'
  mask_version: MV-07B0
communication_objects:
  - id: mdt_o-1
    number: 1
    name: Kanal A Auf/Ab
    function: Langzeit / Fahrbefehl
    dpt: 1.008
    size: 1 Bit
    flags: { communication: true, read: false, write: true, transmit: false, update: false }
  - id: mdt_o-2
    number: 2
    name: Kanal A Lamelle/Stopp
    function: Kurzzeit / Stopp
    dpt: 1.007
    size: 1 Bit
    flags: { communication: true, read: false, write: true, transmit: false, update: false }
  - id: mdt_o-3
    number: 3
    name: Kanal A Position absolut
    function: Höhe in %
    dpt: 5.001
    size: 1 Byte
    flags: { communication: true, read: false, write: true, transmit: false, update: false }
  - id: mdt_o-4
    number: 4
    name: Kanal A Status Höhe
    function: Rückmeldung Höhe
    dpt: 5.001
    size: 1 Byte
    flags: { communication: true, read: true, write: false, transmit: true, update: false }
parameters:
  - id: mdt_p-1
    name: Betriebsart Kanal A
    text: Betriebsart Kanal A
    type: enum
    default: 'shutter'
    options:
      - { value: 'shutter', text: Jalousie mit Lamelle }
      - { value: 'blind', text: Rollladen }
    page: Kanal A > Allgemein
  - id: mdt_p-2
    name: Fahrzeit Auf/Ab (Sekunden)
    text: Fahrzeit Auf/Ab
    type: number
    default: 45
    page: Kanal A > Fahrzeiten
    section: Grundfahrzeit
`,
  hvac: `$schema: https://konfix.sduni.de/schemas/konfix-device-v1.json
konfix_version: '1.0'
manufacturer:
  code: openknx
  name: OpenKNX Community
device:
  order_number: OFM-RTR-01
  name: Raumtemperaturregler
  description: Integrierter PI-Temperaturregler mit Betriebsartenumschaltung
  hardware:
    name: OFM-RTR
    version: '1.0'
    bus_current_ma: 8.0
application:
  id: openknx_rtr-01_v1
  name: RTR Heizung/Kühlung
  version: '1.0'
  mask_version: MV-07B0
communication_objects:
  - id: openknx_o-1
    number: 1
    name: Ist-Temperatur
    function: Temperaturwert
    dpt: 9.001
    size: 2 Bytes
    flags: { communication: true, read: false, write: true, transmit: false, update: false }
  - id: openknx_o-2
    number: 2
    name: Soll-Temperatur Basis
    function: Basis-Sollwert
    dpt: 9.001
    size: 2 Bytes
    flags: { communication: true, read: true, write: true, transmit: true, update: false }
  - id: openknx_o-3
    number: 3
    name: Stellgröße Heizen
    function: Stellwert PI (PWM / stetig)
    dpt: 5.001
    size: 1 Byte
    flags: { communication: true, read: true, write: false, transmit: true, update: false }
parameters:
  - id: openknx_p-1
    name: Reglertyp
    text: Reglertyp
    type: enum
    default: 'pi_continuous'
    options:
      - { value: 'pi_continuous', text: PI-Regler stetig (0-100%) }
      - { value: 'pi_pwm', text: PI-Regler schaltend (PWM) }
      - { value: '2point', text: 2-Punkt-Regler }
    page: Regler > Allgemein
  - id: openknx_p-2
    name: Basis-Solltemperatur (°C)
    text: Basis-Solltemperatur
    type: number
    default: 21.0
    page: Regler > Sollwerte
`,
  binary_input: `$schema: https://konfix.sduni.de/schemas/konfix-device-v1.json
konfix_version: '1.0'
manufacturer:
  code: abb
  name: ABB Stotz-Kontakt
device:
  order_number: US/U4.2
  name: Tasterschnittstelle 4-fach
  description: 4-Kanal Universalschnittstelle für potenzialfreie Kontakte
  hardware:
    name: US/U
    version: '1.0'
    bus_current_ma: 6.0
application:
  id: abb_us-u4-2_v1
  name: Binäreingang 4-fach
  version: '1.0'
  mask_version: MV-07B0
communication_objects:
  - id: abb_o-1
    number: 1
    name: Kanal A Schalten
    function: Eingang A Ein/Aus
    dpt: 1.001
    size: 1 Bit
    flags: { communication: true, read: true, write: false, transmit: true, update: false }
  - id: abb_o-2
    number: 2
    name: Kanal B Schalten
    function: Eingang B Ein/Aus
    dpt: 1.001
    size: 1 Bit
    flags: { communication: true, read: true, write: false, transmit: true, update: false }
parameters:
  - id: abb_p-1
    name: Funktion Kanal A
    text: Funktion Kanal A
    type: enum
    default: 'switch'
    options:
      - { value: 'switch', text: Schalter }
      - { value: 'button', text: Taster }
      - { value: 'dimmer', text: Dimmen }
    page: Kanal A > Allgemein
`,
  blank: `$schema: https://konfix.sduni.de/schemas/konfix-device-v1.json
konfix_version: '1.0'
manufacturer:
  code: custom
  name: Mein Hersteller
device:
  order_number: DEV-001
  name: Neues Gerät
  description: Gerätebeschreibung hier einfügen
  hardware:
    name: DEV-001
    version: '1.0'
    bus_current_ma: 10.0
application:
  id: custom_dev-001_v1
  name: Applikation 1.0
  version: '1.0'
  mask_version: MV-07B0
communication_objects: []
parameters: []
`
};

let editorState = {
  activeTab: "general", // "general", "objects", "params"
  isSyncing: false,
  doc: null,
  koSearch: "",
  koPage: 1,
  koPageSize: 50,
  paramSearch: "",
  paramPageFilter: "",
  paramPage: 1,
  paramPageSize: 50,
  debounceTimeout: null
};

function ensureDocInit() {
  if (!editorState.doc || typeof editorState.doc !== "object") {
    editorState.doc = {
      $schema: "https://konfix.sduni.de/schemas/konfix-device-v1.json",
      konfix_version: "1.0",
      manufacturer: { code: "custom", name: "Mein Hersteller" },
      device: { order_number: "DEV-001", name: "Neues Gerät", hardware: { name: "DEV-001", version: "1.0", bus_current_ma: 10.0 } },
      application: { id: "custom_dev-001_v1", name: "Neues Gerät", version: "1.0", mask_version: "MV-07B0" },
      communication_objects: [],
      parameters: []
    };
  }
  if (!editorState.doc.manufacturer) editorState.doc.manufacturer = {};
  if (!editorState.doc.device) editorState.doc.device = {};
  if (!editorState.doc.device.hardware) editorState.doc.device.hardware = {};
  if (!editorState.doc.application) editorState.doc.application = {};
  if (!Array.isArray(editorState.doc.communication_objects)) editorState.doc.communication_objects = [];
  if (!Array.isArray(editorState.doc.parameters)) editorState.doc.parameters = [];
}

function setupEditorModal() {
  const openEditorNavBtn = document.getElementById("openEditorNavBtn");
  const editorModal = document.getElementById("editorModal");
  const closeEditorBtn = document.getElementById("closeEditorBtn");
  const templateSelect = document.getElementById("editorTemplateSelect");
  const openFileBtn = document.getElementById("editorOpenFileBtn");
  const fileInput = document.getElementById("editorFileInput");
  const copyBtn = document.getElementById("editorCopyBtn");
  const downloadBtn = document.getElementById("editorDownloadBtn");
  const formatBtn = document.getElementById("editorFormatBtn");
  const textarea = document.getElementById("editorYamlTextarea");

  // Nav buttons
  if (openEditorNavBtn && editorModal) {
    openEditorNavBtn.addEventListener("click", () => {
      openEditor();
    });
  }

  if (closeEditorBtn && editorModal) {
    closeEditorBtn.addEventListener("click", () => {
      editorModal.classList.remove("open");
    });
  }

  // Template change
  if (templateSelect) {
    templateSelect.addEventListener("change", (e) => {
      const tpl = EDITOR_TEMPLATES[e.target.value];
      if (tpl) {
        setEditorYamlContent(tpl);
      }
    });
  }

  // File Open
  if (openFileBtn && fileInput) {
    openFileBtn.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (evt) => {
        setEditorYamlContent(evt.target.result);
        e.target.value = "";
      };
      reader.readAsText(file);
    });
  }

  // Copy YAML
  if (copyBtn && textarea) {
    copyBtn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(textarea.value);
        const prev = copyBtn.textContent;
        copyBtn.textContent = "✅ Kopiert!";
        setTimeout(() => copyBtn.textContent = prev, 2000);
      } catch (_) {
        alert("Fehler beim Kopieren in die Zwischenablage");
      }
    });
  }

  // Download YAML
  if (downloadBtn && textarea) {
    downloadBtn.addEventListener("click", () => {
      const orderNoInput = document.getElementById("edOrderNumber");
      const orderNo = (orderNoInput && orderNoInput.value.trim()) || "device";
      const blob = new Blob([textarea.value], { type: "text/yaml;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${orderNo.replace(/[/\\?%*:|"<>]/g, "_")}.yaml`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    });
  }

  // Format YAML
  if (formatBtn && textarea) {
    formatBtn.addEventListener("click", () => {
      syncFormToYaml();
    });
  }

  // Textarea input event (Code -> GUI Sync)
  if (textarea) {
    textarea.addEventListener("input", () => {
      clearTimeout(editorState.debounceTimeout);
      editorState.debounceTimeout = setTimeout(() => {
        saveDraftToStorage(textarea.value);
        validateAndSyncYamlToForm(textarea.value);
      }, 350);
    });

    // Support Tab key in textarea
    textarea.addEventListener("keydown", (e) => {
      if (e.key === "Tab") {
        e.preventDefault();
        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        textarea.value = textarea.value.substring(0, start) + "  " + textarea.value.substring(end);
        textarea.selectionStart = textarea.selectionEnd = start + 2;
        textarea.dispatchEvent(new Event("input"));
      }
    });
  }

  // Tab switching inside Editor Left Pane
  setupEditorTabs();

  // General Form Input change events (GUI -> Code Sync)
  const generalInputs = [
    "edMfgName", "edMfgCode", "edOrderNumber", "edDevName",
    "edDescription", "edHwName", "edHwVersion", "edBusCurrent",
    "edAppId", "edAppVersion"
  ];
  generalInputs.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener("input", () => {
        if (!editorState.isSyncing) {
          syncFormToYaml();
        }
      });
    }
  });

  // Search & Filtering listeners
  const koSearchInput = document.getElementById("editorKoSearch");
  if (koSearchInput) {
    koSearchInput.addEventListener("input", (e) => {
      editorState.koSearch = e.target.value.trim().toLowerCase();
      editorState.koPage = 1;
      renderKoCards();
    });
  }

  const paramSearchInput = document.getElementById("editorParamSearch");
  if (paramSearchInput) {
    paramSearchInput.addEventListener("input", (e) => {
      editorState.paramSearch = e.target.value.trim().toLowerCase();
      editorState.paramPage = 1;
      renderParamCards();
    });
  }

  const paramPageFilter = document.getElementById("editorParamPageFilter");
  if (paramPageFilter) {
    paramPageFilter.addEventListener("change", (e) => {
      editorState.paramPageFilter = e.target.value;
      editorState.paramPage = 1;
      renderParamCards();
    });
  }

  // Add Item Buttons
  const addKoBtn = document.getElementById("editorAddKoBtn");
  if (addKoBtn) {
    addKoBtn.addEventListener("click", () => {
      ensureDocInit();
      const kos = editorState.doc.communication_objects;
      const nextNum = kos.length > 0 ? Math.max(...kos.map(k => k.number || 0)) + 1 : 1;
      const mfg = getMfgCode();
      kos.push({
        id: `${mfg}_o-${nextNum}`,
        number: nextNum,
        name: `Kanal ${String.fromCharCode(64 + Math.min(nextNum, 26))} Schalten`,
        function: "Ein/Aus",
        dpt: "1.001",
        size: "1 Bit",
        flags: { communication: true, read: false, write: true, transmit: false, update: false }
      });
      editorState.koPage = Math.ceil(kos.length / editorState.koPageSize) || 1;
      renderKoCards();
      syncFormToYaml();
    });
  }

  const addParamBtn = document.getElementById("editorAddParamBtn");
  if (addParamBtn) {
    addParamBtn.addEventListener("click", () => {
      ensureDocInit();
      const params = editorState.doc.parameters;
      const nextNum = params.length + 1;
      const mfg = getMfgCode();
      params.push({
        id: `${mfg}_p-${nextNum}`,
        name: `Parameter ${nextNum}`,
        text: `Parameter ${nextNum}`,
        type: "number",
        default: 0,
        page: "Allgemein"
      });
      editorState.paramPage = Math.ceil(params.length / editorState.paramPageSize) || 1;
      updateParamIdDatalist();
      updateParamPageFilterOptions();
      renderParamCards();
      syncFormToYaml();
    });
  }
}

function openEditor() {
  const editorModal = document.getElementById("editorModal");
  if (!editorModal) return;

  const saved = localStorage.getItem("konfix_sandbox_yaml");
  if (saved && saved.trim()) {
    setEditorYamlContent(saved);
  } else {
    setEditorYamlContent(EDITOR_TEMPLATES.switch);
  }

  editorModal.classList.add("open");
}

function openDeviceInSandbox(orderNumber) {
  const editorModal = document.getElementById("editorModal");
  if (!editorModal) return;

  const saveStatus = document.getElementById("editorSaveStatus");
  if (saveStatus) saveStatus.textContent = `Lade ${orderNumber}...`;

  fetch(`/api/v1/devices/yaml?order_number=${encodeURIComponent(orderNumber)}`)
    .then(res => {
      if (!res.ok) throw new Error("Fehler beim Laden");
      return res.text();
    })
    .then(yamlText => {
      setEditorYamlContent(yamlText);
      editorModal.classList.add("open");
      if (saveStatus) saveStatus.textContent = `Geladen aus Katalog: ${orderNumber}`;
    })
    .catch(err => {
      alert(`Konnte Gerät nicht in den Editor laden: ${err.message}`);
    });
}

function setEditorYamlContent(yamlText) {
  const textarea = document.getElementById("editorYamlTextarea");
  if (textarea) {
    textarea.value = yamlText;
    saveDraftToStorage(yamlText);
    editorState.koPage = 1;
    editorState.paramPage = 1;
    editorState.koSearch = "";
    editorState.paramSearch = "";
    editorState.paramPageFilter = "";
    const koSearchEl = document.getElementById("editorKoSearch");
    if (koSearchEl) koSearchEl.value = "";
    const pSearchEl = document.getElementById("editorParamSearch");
    if (pSearchEl) pSearchEl.value = "";
    validateAndSyncYamlToForm(yamlText);
  }
}

function saveDraftToStorage(yamlText) {
  try {
    localStorage.setItem("konfix_sandbox_yaml", yamlText);
    const saveStatus = document.getElementById("editorSaveStatus");
    if (saveStatus) {
      saveStatus.textContent = "✓ Automatisch lokal gespeichert";
      saveStatus.style.color = "#10b981";
    }
  } catch (_) {}
}

function setupEditorTabs() {
  const tabGen = document.getElementById("tabEditorGeneralBtn");
  const tabObj = document.getElementById("tabEditorObjectsBtn");
  const tabParam = document.getElementById("tabEditorParamsBtn");
  const paneGen = document.getElementById("editorTabGeneral");
  const paneObj = document.getElementById("editorTabObjects");
  const paneParam = document.getElementById("editorTabParams");

  function switchTab(active) {
    [tabGen, tabObj, tabParam].forEach(t => {
      if (t) {
        t.classList.remove("btn-primary");
        t.classList.add("btn-secondary");
      }
    });
    [paneGen, paneObj, paneParam].forEach(p => {
      if (p) p.style.display = "none";
    });

    if (active === "general") {
      if (tabGen) { tabGen.classList.add("btn-primary"); tabGen.classList.remove("btn-secondary"); }
      if (paneGen) paneGen.style.display = "block";
    } else if (active === "objects") {
      if (tabObj) { tabObj.classList.add("btn-primary"); tabObj.classList.remove("btn-secondary"); }
      if (paneObj) paneObj.style.display = "block";
    } else if (active === "params") {
      if (tabParam) { tabParam.classList.add("btn-primary"); tabParam.classList.remove("btn-secondary"); }
      if (paneParam) paneParam.style.display = "block";
    }
    editorState.activeTab = active;
  }

  if (tabGen) tabGen.addEventListener("click", () => switchTab("general"));
  if (tabObj) tabObj.addEventListener("click", () => switchTab("objects"));
  if (tabParam) tabParam.addEventListener("click", () => switchTab("params"));
}

function getMfgCode() {
  const el = document.getElementById("edMfgCode");
  const val = (el && el.value.trim().toLowerCase()) || "custom";
  return val.replace(/[^a-z0-9_-]/g, "-") || "custom";
}

function parseYamlDoc(yamlStr) {
  if (typeof jsyaml === "undefined") {
    throw new Error("js-yaml Parser-Bibliothek nicht geladen");
  }
  const data = jsyaml.load(yamlStr);
  if (!data || typeof data !== "object") {
    throw new Error("YAML ist leer oder kein gültiges Objekt");
  }
  data.manufacturer = data.manufacturer || {};
  data.device = data.device || {};
  data.device.hardware = data.device.hardware || {};
  data.application = data.application || {};
  data.communication_objects = Array.isArray(data.communication_objects) ? data.communication_objects : [];
  data.parameters = Array.isArray(data.parameters) ? data.parameters : [];
  return data;
}

function validateAndSyncYamlToForm(yamlText) {
  const badge = document.getElementById("editorValidationBadge");
  const errBox = document.getElementById("editorErrorBox");

  try {
    const data = parseYamlDoc(yamlText);
    editorState.doc = data;

    // Validation checks
    const mfg = data.manufacturer || {};
    const dev = data.device || {};

    if (!mfg.code || !mfg.name || !dev.order_number || !dev.name) {
      if (badge) {
        badge.textContent = "⚠️ Unvollständig";
        badge.style.background = "rgba(245,158,11,0.2)";
        badge.style.color = "#f59e0b";
      }
      if (errBox) {
        errBox.style.display = "block";
        errBox.textContent = "Pflichtfelder fehlen: manufacturer.code, manufacturer.name, device.order_number, device.name";
      }
    } else {
      if (badge) {
        badge.textContent = "✓ Schema v1 valide";
        badge.style.background = "rgba(16,185,129,0.2)";
        badge.style.color = "#10b981";
      }
      if (errBox) errBox.style.display = "none";
    }

    // Populate GUI fields
    editorState.isSyncing = true;

    setVal("edMfgName", mfg.name || "");
    setVal("edMfgCode", (mfg.code || "").toLowerCase());
    setVal("edOrderNumber", dev.order_number || "");
    setVal("edDevName", dev.name || "");
    setVal("edDescription", dev.description || "");
    setVal("edHwName", (dev.hardware && dev.hardware.name) || dev.name || "");
    setVal("edHwVersion", (dev.hardware && dev.hardware.version) || "1.0");
    setVal("edBusCurrent", (dev.hardware && dev.hardware.bus_current_ma) || "10.0");
    setVal("edAppId", (data.application && data.application.id) || "");
    setVal("edAppVersion", (data.application && data.application.version) || "1.0");

    updateParamIdDatalist();
    updateParamPageFilterOptions();
    renderKoCards();
    renderParamCards();

    editorState.isSyncing = false;

  } catch (err) {
    if (badge) {
      badge.textContent = "❌ Syntaxfehler";
      badge.style.background = "rgba(239,68,68,0.2)";
      badge.style.color = "#ef4444";
    }
    if (errBox) {
      errBox.style.display = "block";
      errBox.textContent = err.message;
    }
  }
}

function setVal(id, val) {
  const el = document.getElementById(id);
  if (el) el.value = val;
}

function updateParamIdDatalist() {
  const dl = document.getElementById("editorParamIdDatalist");
  if (!dl || !editorState.doc || !Array.isArray(editorState.doc.parameters)) return;
  dl.innerHTML = editorState.doc.parameters.map(p => {
    const id = p.id || "";
    const name = p.name || p.text || "";
    return `<option value="${escapeHtml(id)}">${escapeHtml(id)}${name ? ' (' + escapeHtml(name) + ')' : ''}</option>`;
  }).join("");
}

function getItemConditions(item) {
  if (!item) return null;
  if (Array.isArray(item.conditions)) return item.conditions;
  if (item.depends_on) {
    if (Array.isArray(item.depends_on.conditions)) return item.depends_on.conditions;
    if (item.depends_on.param_id) return [item.depends_on];
  }
  return null;
}

function formatConditionsSummary(item) {
  const conds = getItemConditions(item);
  if (!conds || !Array.isArray(conds) || conds.length === 0) return null;
  return conds.map(c => {
    const p = c.param_id || c.parameter || "param";
    let vals = "";
    if (Array.isArray(c.when_values)) {
      vals = c.when_values.join(", ");
    } else if (c.value != null) {
      vals = String(c.value);
    } else {
      vals = "*";
    }
    return `${p} = [${vals}]`;
  }).join("; ");
}

function renderConditionsEditorHtml(type, realIdx, item) {
  const conds = getItemConditions(item);
  const hasConds = Array.isArray(conds) && conds.length > 0;

  if (!hasConds) {
    return `
      <div style="margin-top: 0.5rem; display: flex; justify-content: flex-end;">
        <button type="button" class="editor-btn-add-cond" onclick="addConditionItem('${type}', ${realIdx})">
          ⚡ Bedingung hinzufügen
        </button>
      </div>
    `;
  }

  const rows = conds.map((cond, condIdx) => {
    const paramId = cond.param_id || "";
    const whenVals = Array.isArray(cond.when_values) ? cond.when_values.map(String) : (cond.value != null ? [String(cond.value)] : []);
    const valsStr = whenVals.join(", ");

    let quickPillsHtml = "";
    if (paramId && editorState.doc && Array.isArray(editorState.doc.parameters)) {
      const targetParam = editorState.doc.parameters.find(p => p.id === paramId);
      if (targetParam && Array.isArray(targetParam.options) && targetParam.options.length > 0) {
        quickPillsHtml = `
          <div style="grid-column: 1 / -1; display: flex; flex-wrap: wrap; gap: 0.25rem; align-items: center; margin-top: 0.25rem; padding-top: 0.25rem; border-top: 1px dashed rgba(255,255,255,0.06);">
            <span style="font-size: 0.68rem; color: #94a3b8;">Werte anklicken:</span>
            ${targetParam.options.map(o => {
              const oVal = typeof o === "object" ? String(o.value != null ? o.value : o.text) : String(o);
              const oTxt = typeof o === "object" ? String(o.text || o.name || o.value) : String(o);
              const isSelected = whenVals.includes(oVal);
              return `
                <span class="editor-cond-pill ${isSelected ? 'active' : ''}"
                  onclick="toggleConditionValue('${type}', ${realIdx}, ${condIdx}, '${escapeHtml(oVal)}')"
                  title="${isSelected ? 'Klicken zum Abwählen' : 'Klicken zum Auswählen'}">
                  ${escapeHtml(oVal)}${oTxt && oTxt !== oVal ? ' (' + escapeHtml(oTxt) + ')' : ''}
                </span>
              `;
            }).join("")}
          </div>
        `;
      }
    }

    return `
      <div class="editor-cond-row">
        <div>
          <label class="editor-label" style="font-size: 0.7rem;">Ziel-Parameter (param_id)</label>
          <input type="text" class="editor-input" list="editorParamIdDatalist" style="font-size: 0.78rem; padding: 0.25rem 0.5rem;"
            value="${escapeHtml(paramId)}" placeholder="z. B. m-0002_p-12"
            onchange="updateConditionParamId('${type}', ${realIdx}, ${condIdx}, this.value)">
        </div>
        <div>
          <label class="editor-label" style="font-size: 0.7rem;">Wenn Wert (when_values)</label>
          <input type="text" class="editor-input" style="font-size: 0.78rem; padding: 0.25rem 0.5rem;"
            value="${escapeHtml(valsStr)}" placeholder="z. B. 1, 2"
            onchange="updateConditionValues('${type}', ${realIdx}, ${condIdx}, this.value)">
        </div>
        <div style="padding-top: 1.1rem;">
          <button type="button" class="editor-btn-delete" title="Bedingung löschen"
            onclick="removeConditionItem('${type}', ${realIdx}, ${condIdx})">&times;</button>
        </div>
        ${quickPillsHtml}
      </div>
    `;
  }).join("");

  return `
    <div class="editor-cond-box">
      <div class="editor-cond-header">
        <span class="editor-cond-title">⚡ Bedingungen (Sichtbarkeit &amp; Aktivierung)</span>
        <button type="button" class="btn btn-sm btn-ghost" style="font-size: 0.7rem; padding: 0.15rem 0.4rem;"
          onclick="addConditionItem('${type}', ${realIdx})">➕ Bedingung</button>
      </div>
      <div>${rows}</div>
    </div>
  `;
}

function renderPaginationBar(containerId, currentPage, totalPages, totalItems, label, onPageFnName) {
  const el = document.getElementById(containerId);
  if (!el) return;
  if (totalItems === 0) {
    el.style.display = "none";
    return;
  }
  el.style.display = "flex";
  const startItem = (currentPage - 1) * 50 + 1;
  const endItem = Math.min(currentPage * 50, totalItems);

  if (totalPages <= 1) {
    el.innerHTML = `
      <span>${totalItems} ${label}</span>
      <span style="font-size: 0.75rem; color: #64748b;">Seite 1 von 1</span>
    `;
    return;
  }

  el.innerHTML = `
    <span>Zeige ${startItem}–${endItem} von ${totalItems} ${label}</span>
    <div class="editor-pagination-buttons">
      <button type="button" onclick="${onPageFnName}(1)" ${currentPage === 1 ? "disabled" : ""} title="Erste Seite">&laquo;</button>
      <button type="button" onclick="${onPageFnName}(${currentPage - 1})" ${currentPage === 1 ? "disabled" : ""} title="Vorherige Seite">&lsaquo; Zurück</button>
      <span style="padding: 0 0.4rem; font-weight: 600; color: #f8fafc; font-size: 0.8rem;">${currentPage} / ${totalPages}</span>
      <button type="button" onclick="${onPageFnName}(${currentPage + 1})" ${currentPage === totalPages ? "disabled" : ""} title="Nächste Seite">Weiter &rsaquo;</button>
      <button type="button" onclick="${onPageFnName}(${totalPages})" ${currentPage === totalPages ? "disabled" : ""} title="Letzte Seite">&raquo;</button>
    </div>
  `;
}

function renderKoCards() {
  const list = document.getElementById("editorKoList");
  const countBadge = document.getElementById("editorKoCount");
  ensureDocInit();
  const allKos = editorState.doc.communication_objects;
  if (countBadge) countBadge.textContent = allKos.length;
  if (!list) return;

  const query = editorState.koSearch;
  let items = [];
  for (let i = 0; i < allKos.length; i++) {
    const ko = allKos[i];
    if (query) {
      const match = String(ko.number || "").includes(query) ||
        String(ko.id || "").toLowerCase().includes(query) ||
        String(ko.name || "").toLowerCase().includes(query) ||
        String(ko.function || "").toLowerCase().includes(query) ||
        String(ko.dpt || "").toLowerCase().includes(query);
      if (!match) continue;
    }
    items.push({ ko, realIdx: i });
  }

  const totalItems = items.length;
  const totalPages = Math.ceil(totalItems / editorState.koPageSize) || 1;
  if (editorState.koPage > totalPages) editorState.koPage = totalPages;
  if (editorState.koPage < 1) editorState.koPage = 1;

  renderPaginationBar("editorKoPagination", editorState.koPage, totalPages, totalItems, "Objekte", "setKoPage");
  renderPaginationBar("editorKoPaginationBottom", editorState.koPage, totalPages, totalItems, "Objekte", "setKoPage");

  if (totalItems === 0) {
    list.innerHTML = `<div style="color: #64748b; font-size: 0.82rem; padding: 1.5rem; text-align: center; border: 1px dashed rgba(255,255,255,0.1); border-radius: 6px;">Keine Kommunikationsobjekte gefunden ${query ? 'für die Suche "' + escapeHtml(query) + '"' : ''}.</div>`;
    return;
  }

  const startIdx = (editorState.koPage - 1) * editorState.koPageSize;
  const pageItems = items.slice(startIdx, startIdx + editorState.koPageSize);

  list.innerHTML = pageItems.map(({ ko, realIdx }) => {
    const condSummary = formatConditionsSummary(ko);
    const flags = ko.flags || { communication: true, read: false, write: true, transmit: false, update: false };
    const condHtml = renderConditionsEditorHtml("ko", realIdx, ko);

    return `
      <div class="editor-item-card" data-real-idx="${realIdx}">
        <div class="editor-item-header">
          <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
            <span class="editor-item-title">#${ko.number != null ? ko.number : realIdx + 1} &bull; ${escapeHtml(ko.id || '')}</span>
            ${condSummary ? `<span class="editor-badge-cond" title="${escapeHtml(condSummary)}">⚡ ${escapeHtml(condSummary)}</span>` : ''}
          </div>
          <button type="button" class="editor-btn-delete" title="Löschen" onclick="deleteKoItem(${realIdx})">&times; Löschen</button>
        </div>
        <div style="display: grid; grid-template-columns: 80px 1fr 1fr; gap: 0.5rem; margin-bottom: 0.5rem;">
          <div>
            <label class="editor-label">KO-Nr.</label>
            <input type="number" class="editor-input" value="${ko.number != null ? ko.number : realIdx + 1}" oninput="updateKoField(${realIdx}, 'number', parseInt(this.value, 10) || 0)">
          </div>
          <div>
            <label class="editor-label">Name / Kanal</label>
            <input type="text" class="editor-input" value="${escapeHtml(ko.name || '')}" oninput="updateKoField(${realIdx}, 'name', this.value)">
          </div>
          <div>
            <label class="editor-label">Funktion</label>
            <input type="text" class="editor-input" value="${escapeHtml(ko.function || '')}" oninput="updateKoField(${realIdx}, 'function', this.value)">
          </div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; margin-bottom: 0.5rem;">
          <div>
            <label class="editor-label">DPT (z. B. 1.001)</label>
            <input type="text" class="editor-input" value="${escapeHtml(ko.dpt || '1.001')}" oninput="updateKoField(${realIdx}, 'dpt', this.value)">
          </div>
          <div>
            <label class="editor-label">Größe (z. B. 1 Bit)</label>
            <input type="text" class="editor-input" value="${escapeHtml(ko.size || '1 Bit')}" oninput="updateKoField(${realIdx}, 'size', this.value)">
          </div>
        </div>
        <div style="display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap; padding-top: 0.25rem; font-size: 0.75rem; color: #94a3b8;">
          <span style="font-weight: 500;">Flags:</span>
          <label style="display: inline-flex; align-items: center; gap: 0.25rem; cursor: pointer;">
            <input type="checkbox" ${flags.communication ? 'checked' : ''} onchange="updateKoField(${realIdx}, 'flags.communication', this.checked)"> C
          </label>
          <label style="display: inline-flex; align-items: center; gap: 0.25rem; cursor: pointer;">
            <input type="checkbox" ${flags.read ? 'checked' : ''} onchange="updateKoField(${realIdx}, 'flags.read', this.checked)"> R
          </label>
          <label style="display: inline-flex; align-items: center; gap: 0.25rem; cursor: pointer;">
            <input type="checkbox" ${flags.write ? 'checked' : ''} onchange="updateKoField(${realIdx}, 'flags.write', this.checked)"> W
          </label>
          <label style="display: inline-flex; align-items: center; gap: 0.25rem; cursor: pointer;">
            <input type="checkbox" ${flags.transmit ? 'checked' : ''} onchange="updateKoField(${realIdx}, 'flags.transmit', this.checked)"> T
          </label>
          <label style="display: inline-flex; align-items: center; gap: 0.25rem; cursor: pointer;">
            <input type="checkbox" ${flags.update ? 'checked' : ''} onchange="updateKoField(${realIdx}, 'flags.update', this.checked)"> U
          </label>
        </div>
        ${condHtml}
      </div>
    `;
  }).join("");
}

function updateParamPageFilterOptions() {
  const select = document.getElementById("editorParamPageFilter");
  if (!select || !editorState.doc || !editorState.doc.parameters) return;
  const currentVal = editorState.paramPageFilter;
  const pageMap = new Map();
  editorState.doc.parameters.forEach(p => {
    const pg = (p.page && typeof p.page === "string" ? p.page.trim() : "");
    if (pg) {
      pageMap.set(pg, (pageMap.get(pg) || 0) + 1);
    }
  });

  const sortedPages = Array.from(pageMap.keys()).sort();
  select.innerHTML = `<option value="">Alle Seiten / Menüs (${editorState.doc.parameters.length})</option>` +
    sortedPages.map(pg => `
      <option value="${escapeHtml(pg)}" ${pg === currentVal ? "selected" : ""}>${escapeHtml(pg)} (${pageMap.get(pg)})</option>
    `).join("");
}

function renderParamOptionsHtml(param) {
  if (!param.options || !Array.isArray(param.options) || param.options.length === 0) {
    if (param.type === "enum") {
      return `<div style="font-size: 0.75rem; color: #f59e0b; margin-top: 0.35rem;">⚠️ Keine Optionen definiert für enum</div>`;
    }
    return "";
  }
  const opts = param.options;
  const pills = opts.map(o => {
    let val = "";
    let txt = "";
    if (o && typeof o === "object") {
      val = o.value != null ? o.value : o.text;
      txt = o.text || o.name || o.value;
    } else {
      val = o;
      txt = o;
    }
    return `<span class="editor-badge-option" title="Wert: ${escapeHtml(String(val))}"><strong>${escapeHtml(String(val))}</strong>: ${escapeHtml(String(txt))}</span>`;
  }).join("");

  return `
    <div class="editor-options-box">
      <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.75rem; color: #94a3b8; margin-bottom: 0.25rem;">
        <span>Auswahloptionen (${opts.length})</span>
      </div>
      <div class="editor-options-list">${pills}</div>
    </div>
  `;
}

function renderParamCards() {
  const list = document.getElementById("editorParamList");
  const countBadge = document.getElementById("editorParamCount");
  ensureDocInit();
  const allParams = editorState.doc.parameters;
  if (countBadge) countBadge.textContent = allParams.length;
  if (!list) return;

  const query = editorState.paramSearch;
  const pageFilter = editorState.paramPageFilter;
  let items = [];

  for (let i = 0; i < allParams.length; i++) {
    const param = allParams[i];
    if (pageFilter && param.page !== pageFilter) continue;
    if (query) {
      const match = String(param.id || "").toLowerCase().includes(query) ||
        String(param.name || "").toLowerCase().includes(query) ||
        String(param.text || "").toLowerCase().includes(query) ||
        String(param.page || "").toLowerCase().includes(query);
      if (!match) continue;
    }
    items.push({ param, realIdx: i });
  }

  const totalItems = items.length;
  const totalPages = Math.ceil(totalItems / editorState.paramPageSize) || 1;
  if (editorState.paramPage > totalPages) editorState.paramPage = totalPages;
  if (editorState.paramPage < 1) editorState.paramPage = 1;

  renderPaginationBar("editorParamPagination", editorState.paramPage, totalPages, totalItems, "Parameter", "setParamPage");
  renderPaginationBar("editorParamPaginationBottom", editorState.paramPage, totalPages, totalItems, "Parameter", "setParamPage");

  if (totalItems === 0) {
    list.innerHTML = `<div style="color: #64748b; font-size: 0.82rem; padding: 1.5rem; text-align: center; border: 1px dashed rgba(255,255,255,0.1); border-radius: 6px;">Keine Parameter gefunden ${query ? 'für die Suche "' + escapeHtml(query) + '"' : ''}.</div>`;
    return;
  }

  const startIdx = (editorState.paramPage - 1) * editorState.paramPageSize;
  const pageItems = items.slice(startIdx, startIdx + editorState.paramPageSize);

  list.innerHTML = pageItems.map(({ param, realIdx }) => {
    const condSummary = formatConditionsSummary(param);
    const optionsHtml = renderParamOptionsHtml(param);
    const ruleCount = Array.isArray(param.assign_rules) ? param.assign_rules.length : 0;
    const hasTrans = param.translations && Object.keys(param.translations).length > 0;
    const condHtml = renderConditionsEditorHtml("param", realIdx, param);

    return `
      <div class="editor-item-card" data-real-idx="${realIdx}">
        <div class="editor-item-header">
          <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
            <span class="editor-item-title">${escapeHtml(param.id || '')}</span>
            ${param.page ? `<span class="editor-meta-pill" title="Menüpfad">📂 ${escapeHtml(param.page)}</span>` : ''}
            ${condSummary ? `<span class="editor-badge-cond" title="${escapeHtml(condSummary)}">⚡ ${escapeHtml(condSummary)}</span>` : ''}
            ${ruleCount > 0 ? `<span class="editor-meta-pill" title="Regeln">⚙️ ${ruleCount} Regeln</span>` : ''}
            ${hasTrans ? `<span class="editor-meta-pill" title="Übersetzungen">🌐 Übersetzt</span>` : ''}
          </div>
          <button type="button" class="editor-btn-delete" title="Löschen" onclick="deleteParamItem(${realIdx})">&times; Löschen</button>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; margin-bottom: 0.5rem;">
          <div>
            <label class="editor-label">ID (lowercase)</label>
            <input type="text" class="editor-input" value="${escapeHtml(param.id || '')}" oninput="updateParamField(${realIdx}, 'id', this.value.toLowerCase())">
          </div>
          <div>
            <label class="editor-label">Bezeichnung / Text</label>
            <input type="text" class="editor-input" value="${escapeHtml(param.name || param.text || '')}" oninput="updateParamField(${realIdx}, 'name', this.value)">
          </div>
        </div>
        <div style="display: grid; grid-template-columns: 130px 1fr 1fr; gap: 0.5rem;">
          <div>
            <label class="editor-label">Typ</label>
            <select class="editor-input" onchange="updateParamField(${realIdx}, 'type', this.value)">
              <option value="number" ${param.type === 'number' ? 'selected' : ''}>Zahl (number)</option>
              <option value="enum" ${param.type === 'enum' ? 'selected' : ''}>Auswahl (enum)</option>
              <option value="text" ${param.type === 'text' ? 'selected' : ''}>Text (text)</option>
              <option value="boolean" ${param.type === 'boolean' ? 'selected' : ''}>Schalter (bool)</option>
              <option value="float" ${param.type === 'float' ? 'selected' : ''}>Fließkomma</option>
            </select>
          </div>
          <div>
            <label class="editor-label">Default-Wert</label>
            <input type="text" class="editor-input" value="${escapeHtml(String(param.default != null ? param.default : ''))}" oninput="updateParamField(${realIdx}, 'default', this.value)">
          </div>
          <div>
            <label class="editor-label">Seite / Menüpfad</label>
            <input type="text" class="editor-input" value="${escapeHtml(param.page || '')}" placeholder="Kanal A > Zeit" oninput="updateParamField(${realIdx}, 'page', this.value)">
          </div>
        </div>
        ${optionsHtml}
        ${condHtml}
      </div>
    `;
  }).join("");
}

// Window functions for inline HTML event handlers
window.deleteKoItem = function(realIdx) {
  ensureDocInit();
  editorState.doc.communication_objects.splice(realIdx, 1);
  renderKoCards();
  syncFormToYaml();
};

window.updateKoField = function(realIdx, field, value) {
  ensureDocInit();
  const ko = editorState.doc.communication_objects[realIdx];
  if (!ko) return;
  if (field.startsWith("flags.")) {
    const flagKey = field.split(".")[1];
    ko.flags = ko.flags || {};
    ko.flags[flagKey] = Boolean(value);
  } else {
    ko[field] = value;
  }
  syncFormToYaml();
};

window.deleteParamItem = function(realIdx) {
  ensureDocInit();
  editorState.doc.parameters.splice(realIdx, 1);
  updateParamIdDatalist();
  updateParamPageFilterOptions();
  renderParamCards();
  syncFormToYaml();
};

window.updateParamField = function(realIdx, field, value) {
  ensureDocInit();
  const param = editorState.doc.parameters[realIdx];
  if (!param) return;
  param[field] = value;
  if (field === "name" && !param.text) {
    param.text = value;
  }
  if (field === "id" || field === "name") {
    updateParamIdDatalist();
  }
  if (field === "page") {
    updateParamPageFilterOptions();
  }
  syncFormToYaml();
};

window.addConditionItem = function(type, realIdx) {
  ensureDocInit();
  const list = type === "ko" ? editorState.doc.communication_objects : editorState.doc.parameters;
  const item = list[realIdx];
  if (!item) return;

  if (!Array.isArray(item.conditions)) {
    if (item.depends_on) {
      if (Array.isArray(item.depends_on.conditions)) {
        item.conditions = [...item.depends_on.conditions];
      } else if (item.depends_on.param_id) {
        item.conditions = [{ param_id: item.depends_on.param_id, when_values: item.depends_on.when_values || ["1"] }];
      } else {
        item.conditions = [];
      }
      delete item.depends_on;
    } else {
      item.conditions = [];
    }
  }

  let defaultParamId = "";
  if (Array.isArray(editorState.doc.parameters) && editorState.doc.parameters.length > 0) {
    defaultParamId = editorState.doc.parameters[0].id || "";
  }

  item.conditions.push({
    param_id: defaultParamId,
    when_values: ["1"]
  });

  if (type === "ko") renderKoCards();
  else renderParamCards();
  syncFormToYaml();
};

window.removeConditionItem = function(type, realIdx, condIdx) {
  ensureDocInit();
  const list = type === "ko" ? editorState.doc.communication_objects : editorState.doc.parameters;
  const item = list[realIdx];
  if (!item) return;

  const conds = getItemConditions(item);
  if (Array.isArray(conds)) {
    conds.splice(condIdx, 1);
    if (conds.length === 0) {
      delete item.conditions;
      delete item.depends_on;
    } else {
      item.conditions = conds;
      delete item.depends_on;
    }
  }

  if (type === "ko") renderKoCards();
  else renderParamCards();
  syncFormToYaml();
};

window.updateConditionParamId = function(type, realIdx, condIdx, newParamId) {
  ensureDocInit();
  const list = type === "ko" ? editorState.doc.communication_objects : editorState.doc.parameters;
  const item = list[realIdx];
  if (!item) return;

  const conds = getItemConditions(item);
  if (Array.isArray(conds) && conds[condIdx]) {
    conds[condIdx].param_id = (newParamId || "").trim();
    item.conditions = conds;
    delete item.depends_on;
  }

  if (type === "ko") renderKoCards();
  else renderParamCards();
  syncFormToYaml();
};

window.updateConditionValues = function(type, realIdx, condIdx, valStr) {
  ensureDocInit();
  const list = type === "ko" ? editorState.doc.communication_objects : editorState.doc.parameters;
  const item = list[realIdx];
  if (!item) return;

  const conds = getItemConditions(item);
  if (Array.isArray(conds) && conds[condIdx]) {
    const rawParts = (valStr || "").split(",").map(s => s.trim()).filter(s => s.length > 0);
    conds[condIdx].when_values = rawParts.length > 0 ? rawParts : ["1"];
    item.conditions = conds;
    delete item.depends_on;
  }

  if (type === "ko") renderKoCards();
  else renderParamCards();
  syncFormToYaml();
};

window.toggleConditionValue = function(type, realIdx, condIdx, optVal) {
  ensureDocInit();
  const list = type === "ko" ? editorState.doc.communication_objects : editorState.doc.parameters;
  const item = list[realIdx];
  if (!item) return;

  const conds = getItemConditions(item);
  if (Array.isArray(conds) && conds[condIdx]) {
    let whenVals = Array.isArray(conds[condIdx].when_values) ? [...conds[condIdx].when_values].map(String) : [];
    const strOptVal = String(optVal);
    const idx = whenVals.indexOf(strOptVal);
    if (idx >= 0) {
      whenVals.splice(idx, 1);
    } else {
      whenVals.push(strOptVal);
    }
    conds[condIdx].when_values = whenVals.length > 0 ? whenVals : ["1"];
    item.conditions = conds;
    delete item.depends_on;
  }

  if (type === "ko") renderKoCards();
  else renderParamCards();
  syncFormToYaml();
};

window.setKoPage = function(pageNum) {
  editorState.koPage = pageNum;
  renderKoCards();
};

window.setParamPage = function(pageNum) {
  editorState.paramPage = pageNum;
  renderParamCards();
};

function syncFormToYaml() {
  if (editorState.isSyncing) return;
  ensureDocInit();

  const mfg = editorState.doc.manufacturer;
  const dev = editorState.doc.device;
  const hw = dev.hardware = dev.hardware || {};
  const app = editorState.doc.application;

  mfg.name = (document.getElementById("edMfgName")?.value || "").trim() || "Mein Hersteller";
  mfg.code = (document.getElementById("edMfgCode")?.value || "").trim().toLowerCase() || "custom";
  dev.order_number = (document.getElementById("edOrderNumber")?.value || "").trim() || "DEV-001";
  dev.name = (document.getElementById("edDevName")?.value || "").trim() || "Neues Gerät";
  
  const desc = (document.getElementById("edDescription")?.value || "").trim();
  if (desc) {
    dev.description = desc;
  } else {
    delete dev.description;
  }

  hw.name = (document.getElementById("edHwName")?.value || "").trim() || dev.name;
  hw.version = (document.getElementById("edHwVersion")?.value || "").trim() || "1.0";
  hw.bus_current_ma = parseFloat(document.getElementById("edBusCurrent")?.value) || 10.0;

  app.id = (document.getElementById("edAppId")?.value || "").trim().toLowerCase() || `${mfg.code}_${dev.order_number.toLowerCase().replace(/[^a-z0-9_-]/g, '-')}`;
  app.name = dev.name;
  app.version = (document.getElementById("edAppVersion")?.value || "").trim() || "1.0";
  if (!app.mask_version) app.mask_version = "MV-07B0";

  if (typeof jsyaml !== "undefined") {
    try {
      const yamlStr = jsyaml.dump(editorState.doc, {
        indent: 2,
        lineWidth: -1,
        noRefs: true,
        sortKeys: false
      });
      const textarea = document.getElementById("editorYamlTextarea");
      if (textarea) {
        textarea.value = yamlStr;
        saveDraftToStorage(yamlStr);
      }
      const badge = document.getElementById("editorValidationBadge");
      if (badge) {
        badge.textContent = "✓ Schema v1 valide";
        badge.style.background = "rgba(16,185,129,0.2)";
        badge.style.color = "#10b981";
      }
      const errBox = document.getElementById("editorErrorBox");
      if (errBox) errBox.style.display = "none";
    } catch (err) {
      const errBox = document.getElementById("editorErrorBox");
      if (errBox) {
        errBox.style.display = "block";
        errBox.textContent = `Fehler beim Erzeugen des YAMLs: ${err.message}`;
      }
    }
  }
}





