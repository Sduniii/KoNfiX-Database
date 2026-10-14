// OpenKNX Toolbox Extra - Client Logic
// Seamlessly integrated with KoNfiX-Catalog

const openknxState = {
  currentTab: "releases",
  releases: {},
  applications: [],
  devices: [],
  gateways: [],
  files: [],
  tasks: [],
  taskPollInterval: null,
  activeFlashTaskId: null,
  flashPollInterval: null,
  selectedXmlFile: null
};

// ==============================================================================
// Helpers & Utilities
// ==============================================================================
function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

function t(key, params = {}) {
  if (typeof I18n !== "undefined" && typeof I18n.t === "function") {
    return I18n.t(key, params);
  }
  return key;
}

// ==============================================================================
// Initialization & Modal Controls
// ==============================================================================
function initOpenKnxToolbox() {
  const modal = document.getElementById("openknxToolboxModal");
  const openBtn = document.getElementById("openOpenKnxToolboxBtn");
  const closeBtn = document.getElementById("closeOpenKnxBtn");

  if (!modal) return;

  if (openBtn) {
    openBtn.addEventListener("click", () => {
      modal.classList.add("open");
      loadGateways().then(() => {
        switchTab(openknxState.currentTab || "releases");
      });
      startTaskPolling();
    });
  }

  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      modal.classList.remove("open");
      stopTaskPolling();
    });
  }

  // Setup Tab Navigation
  const tabBtns = document.querySelectorAll(".openknx-tab-btn");
  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;
      if (tab) switchTab(tab);
    });
  });

  // Setup Sub-Features
  setupReleasesTab();
  setupDevicesTab();
  setupFilesTab();
  setupFlashTab();
  setupGatewaysTab();
  setupKnxprodTab();
  setupTasksTab();
}

function switchTab(tabName) {
  openknxState.currentTab = tabName;

  // Update tab buttons
  document.querySelectorAll(".openknx-tab-btn").forEach(btn => {
    if (btn.dataset.tab === tabName) {
      btn.classList.add("active", "btn-primary");
      btn.classList.remove("btn-secondary");
    } else {
      btn.classList.remove("active", "btn-primary");
      btn.classList.add("btn-secondary");
    }
  });

  // Update panels
  const panels = {
    releases: document.getElementById("openknxTabReleases"),
    devices: document.getElementById("openknxTabDevices"),
    files: document.getElementById("openknxTabFiles"),
    flash: document.getElementById("openknxTabFlash"),
    gateways: document.getElementById("openknxTabGateways"),
    knxprod: document.getElementById("openknxTabKnxprod"),
    tasks: document.getElementById("openknxTabTasks")
  };

  Object.keys(panels).forEach(key => {
    if (panels[key]) {
      panels[key].style.display = key === tabName ? "block" : "none";
    }
  });

  // Tab-specific load actions
  if (tabName === "releases" && Object.keys(openknxState.releases).length === 0) {
    loadReleases();
  } else if (tabName === "devices") {
    loadDevices();
  } else if (tabName === "gateways") {
    loadGateways();
  } else if (tabName === "flash") {
    populateFlashRepos();
  } else if (tabName === "tasks") {
    loadTasks();
  }
}

// ==============================================================================
// TAB 1: Releases & Firmware Hub
// ==============================================================================
function setupReleasesTab() {
  const searchInput = document.getElementById("openknxReleaseSearch");
  const channelSelect = document.getElementById("openknxReleaseChannel");
  const syncBtn = document.getElementById("openknxSyncReleasesBtn");

  if (searchInput) {
    searchInput.addEventListener("input", () => renderReleasesGrid());
  }

  if (channelSelect) {
    channelSelect.addEventListener("change", () => renderReleasesGrid());
  }

  if (syncBtn) {
    syncBtn.addEventListener("click", async () => {
      syncBtn.disabled = true;
      syncBtn.innerHTML = `<span>⏳ Synchronisiere...</span>`;
      try {
        await fetch("/api/v1/openknx/releases/sync", { method: "POST" });
        await loadReleases(true);
      } catch (e) {
        alert("Fehler beim Synchronisieren: " + e.message);
      } finally {
        syncBtn.disabled = false;
        syncBtn.innerHTML = `
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg>
          <span>${t("openknx.releases.refreshBtn")}</span>
        `;
      }
    });
  }
}

async function loadReleases(forceRefresh = false) {
  const grid = document.getElementById("openknxReleasesGrid");
  if (!grid) return;

  grid.innerHTML = `<div style="text-align: center; padding: 3rem; color: #94a3b8;">${t("openknx.releases.loading")}</div>`;

  try {
    const [appsRes, relsRes] = await Promise.all([
      fetch(`/api/v1/openknx/applications?force_refresh=${forceRefresh}`),
      fetch(`/api/v1/openknx/releases?force_refresh=${forceRefresh}`)
    ]);

    openknxState.applications = await appsRes.json();
    openknxState.releases = await relsRes.json();
    renderReleasesGrid();
    populateFlashRepos();
  } catch (err) {
    grid.innerHTML = `
      <div style="grid-column: 1 / -1; padding: 2rem; background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 8px; color: #f87171;">
        Fehler beim Laden der OpenKNX Releases: ${escapeHtml(err.message)}
      </div>
    `;
  }
}

function renderReleasesGrid() {
  const grid = document.getElementById("openknxReleasesGrid");
  if (!grid) return;

  const searchTerm = (document.getElementById("openknxReleaseSearch")?.value || "").toLowerCase().trim();
  const channelFilter = document.getElementById("openknxReleaseChannel")?.value || "all";

  const entries = Object.entries(openknxState.releases || {});
  if (entries.length === 0) {
    grid.innerHTML = `<div style="text-align: center; padding: 3rem; color: #94a3b8;">${t("openknx.releases.noResults")}</div>`;
    return;
  }

  let html = "";
  let matchedCount = 0;

  for (const [repoName, repoData] of entries) {
    if (searchTerm && !repoName.toLowerCase().includes(searchTerm)) {
      continue;
    }

    const releases = repoData.releases || [];
    let displayRelease = null;

    if (channelFilter === "release") {
      displayRelease = releases.find(r => !r.prerelease);
    } else if (channelFilter === "dev") {
      displayRelease = releases.find(r => r.prerelease);
    } else {
      displayRelease = releases[0];
    }

    if (!displayRelease && channelFilter !== "all") {
      continue;
    }

    matchedCount++;
    const tag = displayRelease ? displayRelease.tag_name : "v0.0.0";
    const isPre = displayRelease ? displayRelease.prerelease : false;
    const assets = displayRelease ? displayRelease.assets || [] : [];
    const dateStr = displayRelease?.published_at ? new Date(displayRelease.published_at).toLocaleDateString() : "";

    // Find asset types
    const knxprodAsset = assets.find(a => a.name.endsWith(".knxprod"));
    const xmlAsset = assets.find(a => a.name.endsWith(".xml") && !a.name.includes("knx_master"));
    const binAsset = assets.find(a => a.name.endsWith(".bin") || a.name.endsWith(".hex"));

    html += `
      <div class="openknx-card">
        <div>
          <div class="openknx-card-header">
            <span class="openknx-card-title">${escapeHtml(repoName)}</span>
            <span class="badge ${isPre ? 'badge-update' : 'badge-uptodate'}">
              ${isPre ? 'Beta / Dev' : 'Stable'}
            </span>
          </div>
          <div class="openknx-card-meta">
            <span style="font-family: monospace; color: #38bdf8;">${escapeHtml(tag)}</span>
            <span>•</span>
            <span>${escapeHtml(dateStr)}</span>
            <span>•</span>
            <a href="https://github.com/OpenKNX/${escapeHtml(repoName)}" target="_blank" rel="noreferrer" style="color: #94a3b8; text-decoration: none;">GitHub ↗</a>
          </div>
          <p class="openknx-card-desc">
            OpenKNX Modul-Definition mit ${assets.length} Download-Assets (Firmware, .knxprod &amp; XML).
          </p>
        </div>

        <div>
          <div class="openknx-card-actions">
            <button type="button" class="btn btn-sm btn-primary openknx-import-btn" data-repo="${escapeHtml(repoName)}" data-tag="${escapeHtml(tag)}" style="flex: 1;">
              ⚡ In Katalog importieren
            </button>
            ${knxprodAsset ? `
              <a href="/api/v1/openknx/releases/download-asset?repository=${encodeURIComponent(repoName)}&tag=${encodeURIComponent(tag)}&asset_name=${encodeURIComponent(knxprodAsset.name)}" class="btn btn-sm btn-secondary" title="ETS .knxprod herunterladen">
                📦 .knxprod
              </a>
            ` : ''}
            ${xmlAsset ? `
              <a href="/api/v1/openknx/releases/download-asset?repository=${encodeURIComponent(repoName)}&tag=${encodeURIComponent(tag)}&asset_name=${encodeURIComponent(xmlAsset.name)}" class="btn btn-sm btn-secondary" title="OpenKNX XML Metadaten">
                📄 XML
              </a>
            ` : ''}
            ${binAsset ? `
              <a href="/api/v1/openknx/releases/download-asset?repository=${encodeURIComponent(repoName)}&tag=${encodeURIComponent(tag)}&asset_name=${encodeURIComponent(binAsset.name)}" class="btn btn-sm btn-secondary" title="Firmware Binary herunterladen">
                ⚡ Binary
              </a>
            ` : ''}
          </div>
          <div class="import-status-box" id="importStatus_${escapeHtml(repoName)}" style="display: none; margin-top: 0.5rem; font-size: 0.78rem;"></div>
        </div>
      </div>
    `;
  }

  if (matchedCount === 0) {
    grid.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; padding: 3rem; color: #94a3b8;">${t("openknx.releases.noResults")}</div>`;
    return;
  }

  grid.innerHTML = html;

  // Bind 1-click import buttons
  grid.querySelectorAll(".openknx-import-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const repo = btn.dataset.repo;
      const tag = btn.dataset.tag;
      const statusBox = document.getElementById(`importStatus_${repo}`);
      if (!repo || !tag) return;

      btn.disabled = true;
      const origText = btn.textContent;
      btn.textContent = "⏳ Importiere...";
      if (statusBox) {
        statusBox.style.display = "block";
        statusBox.style.color = "#38bdf8";
        statusBox.textContent = "Lade Release herunter, parse XML und erzeuge KoNfiX-Geräte...";
      }

      try {
        const res = await fetch("/api/v1/openknx/releases/import", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ repository: repo, tag: tag })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Import fehlgeschlagen");

        btn.textContent = "✅ Importiert!";
        btn.classList.remove("btn-primary");
        btn.classList.add("btn-secondary");
        if (statusBox) {
          statusBox.style.color = "#10b981";
          statusBox.textContent = `✅ Erfolgreich: ${data.devices_created || 1} Gerät(e) angelegt, .yaml & .knxprod erzeugt.`;
        }

        // Trigger refresh of main catalog
        if (typeof loadStats === "function") loadStats();
        if (typeof loadManufacturers === "function") loadManufacturers();
        if (typeof loadDevices === "function") loadDevices();
      } catch (e) {
        btn.disabled = false;
        btn.textContent = origText;
        if (statusBox) {
          statusBox.style.color = "#ef4444";
          statusBox.textContent = "❌ " + e.message;
        }
      }
    });
  });
}

// ==============================================================================
// TAB 2: Device Manager (mDNS & Bus Discovery)
// ==============================================================================
function setupDevicesTab() {
  const scanBtn = document.getElementById("openknxScanMdnsBtn");
  if (scanBtn) {
    scanBtn.addEventListener("click", async () => {
      scanBtn.disabled = true;
      const statusEl = document.getElementById("openknxDeviceScanStatus");
      if (statusEl) statusEl.textContent = t("openknx.devices.scanning");

      try {
        const res = await fetch("/api/v1/openknx/devices/scan-mdns?timeout=3.0", { method: "POST" });
        const data = await res.json();
        if (statusEl) statusEl.textContent = t("openknx.devices.foundDevices", { count: data.found_count || 0 });
        await loadDevices();
      } catch (err) {
        if (statusEl) statusEl.textContent = "Fehler: " + err.message;
      } finally {
        scanBtn.disabled = false;
      }
    });
  }
}

async function loadDevices() {
  const tbody = document.getElementById("openknxDevicesTbody");
  if (!tbody) return;

  try {
    const res = await fetch("/api/v1/openknx/devices");
    const devices = await res.json();
    openknxState.devices = devices;

    if (!devices || devices.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" style="text-align: center; padding: 2.5rem; color: #94a3b8;">
            ${t("openknx.devices.noDevices")}
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = devices.map(d => {
      const isUpToDate = !d.update_available;
      return `
        <tr>
          <td>
            <div style="font-weight: 600; color: #f8fafc;">${escapeHtml(d.device_name || d.name)}</div>
            <div style="font-size: 0.75rem; color: #94a3b8;">${escapeHtml(d.name)}</div>
          </td>
          <td>
            <code style="font-family: monospace; color: #38bdf8; font-weight: 600;">${escapeHtml(d.individual_address || '-')}</code>
          </td>
          <td>
            <span style="font-family: monospace;">${escapeHtml(d.ip || '-')}</span>
          </td>
          <td>
            <span class="badge" style="background: rgba(255,255,255,0.06);">${escapeHtml(d.hardware || d.chip || 'OpenKNX')}</span>
          </td>
          <td>
            <span style="font-family: monospace;">${escapeHtml(d.firmware_version || '-')}</span>
          </td>
          <td>
            ${isUpToDate ? `
              <span class="badge badge-uptodate">v${escapeHtml(d.firmware_version || '1.0')} (Aktuell)</span>
            ` : `
              <span class="badge badge-update" title="Update verfügbar">
                ⚡ Neu: v${escapeHtml(d.latest_release_version || '')}
              </span>
            `}
          </td>
          <td style="text-align: right;">
            <div style="display: inline-flex; gap: 0.35rem;">
              ${d.individual_address ? `
                <button type="button" class="btn btn-sm btn-secondary dev-restart-btn" data-addr="${escapeHtml(d.individual_address)}" title="Gerät über KNX-Bus neu starten">
                  🔄
                </button>
                <button type="button" class="btn btn-sm btn-secondary dev-files-btn" data-addr="${escapeHtml(d.individual_address)}" title="Dateimanager für dieses Gerät öffnen">
                  📁
                </button>
              ` : ''}
              <button type="button" class="btn btn-sm btn-primary dev-flash-btn" data-ip="${escapeHtml(d.ip || '')}" data-addr="${escapeHtml(d.individual_address || '')}" title="Firmware flashen">
                ⚡ Flashen
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join("");

    // Restart listeners
    tbody.querySelectorAll(".dev-restart-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const addr = btn.dataset.addr;
        if (!confirm(`Gerät ${addr} jetzt über den KNX-Bus neu starten?`)) return;
        btn.disabled = true;
        try {
          const gwSelect = document.getElementById("openknxDeviceGatewaySelect");
          const gwId = gwSelect && gwSelect.value ? parseInt(gwSelect.value, 10) : null;
          const res = await fetch("/api/v1/openknx/devices/restart", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ target_address: addr, gateway_id: gwId })
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || "Fehler beim Neustart");
          alert("Neustart-Befehl erfolgreich gesendet!");
        } catch (e) {
          alert("Fehler: " + e.message);
        } finally {
          btn.disabled = false;
        }
      });
    });

    // File manager jump
    tbody.querySelectorAll(".dev-files-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const addr = btn.dataset.addr;
        switchTab("files");
        const targetInput = document.getElementById("openknxFileTargetAddress");
        if (targetInput) targetInput.value = addr;
        loadDeviceFiles();
      });
    });

    // Flash jump
    tbody.querySelectorAll(".dev-flash-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const ip = btn.dataset.ip;
        const addr = btn.dataset.addr;
        switchTab("flash");
        if (ip) {
          const ipInput = document.getElementById("openknxFlashIp");
          if (ipInput) ipInput.value = ip;
        }
        if (addr) {
          const addrInput = document.getElementById("openknxFlashKnxAddress");
          if (addrInput) addrInput.value = addr;
        }
      });
    });

  } catch (err) {
    console.error("Fehler beim Laden der OpenKNX Geräte:", err);
  }
}

// ==============================================================================
// TAB 3: KNX File Manager (Object 159 FTM)
// ==============================================================================
function setupFilesTab() {
  const listBtn = document.getElementById("openknxFileListBtn");
  const uploadBtn = document.getElementById("openknxFileUploadBtn");
  const fileInput = document.getElementById("openknxFileInput");
  const mkdirBtn = document.getElementById("openknxFileMkdirBtn");
  const formatBtn = document.getElementById("openknxFileFormatBtn");

  if (listBtn) {
    listBtn.addEventListener("click", () => loadDeviceFiles());
  }

  if (uploadBtn && fileInput) {
    uploadBtn.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", async () => {
      if (!fileInput.files || fileInput.files.length === 0) return;
      const file = fileInput.files[0];
      const targetAddr = document.getElementById("openknxFileTargetAddress")?.value.trim();
      const currentPath = document.getElementById("openknxFilePath")?.value.trim() || "/";
      const gwId = document.getElementById("openknxFileGatewaySelect")?.value;

      if (!targetAddr) {
        alert("Bitte gib zuerst die physikalische KNX-Zieladresse (z. B. 1.1.25) an.");
        return;
      }

      const remotePath = currentPath.endsWith("/") ? currentPath + file.name : currentPath + "/" + file.name;
      const statusBox = document.getElementById("openknxFileStatus");
      if (statusBox) {
        statusBox.style.display = "block";
        statusBox.style.color = "#38bdf8";
        statusBox.textContent = `Übertrage '${file.name}' auf ${targetAddr}:${remotePath}...`;
      }

      const formData = new FormData();
      formData.append("target_address", targetAddr);
      formData.append("remote_path", remotePath);
      if (gwId) formData.append("gateway_id", gwId);
      formData.append("file", file);

      try {
        const res = await fetch("/api/v1/openknx/file-manager/upload", {
          method: "POST",
          body: formData
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Upload fehlgeschlagen");
        if (statusBox) {
          statusBox.style.color = "#10b981";
          statusBox.textContent = `✅ Datei '${file.name}' erfolgreich hochgeladen!`;
        }
        await loadDeviceFiles();
      } catch (e) {
        if (statusBox) {
          statusBox.style.color = "#ef4444";
          statusBox.textContent = "❌ Upload-Fehler: " + e.message;
        }
      } finally {
        fileInput.value = "";
      }
    });
  }

  if (mkdirBtn) {
    mkdirBtn.addEventListener("click", async () => {
      const targetAddr = document.getElementById("openknxFileTargetAddress")?.value.trim();
      const currentPath = document.getElementById("openknxFilePath")?.value.trim() || "/";
      const gwId = document.getElementById("openknxFileGatewaySelect")?.value;
      if (!targetAddr) {
        alert("Bitte gib zuerst die Zieladresse (KNX PA) an.");
        return;
      }
      const dirName = prompt("Name des neuen Ordners:");
      if (!dirName || !dirName.trim()) return;

      const remotePath = currentPath.endsWith("/") ? currentPath + dirName.trim() : currentPath + "/" + dirName.trim();
      try {
        const res = await fetch("/api/v1/openknx/file-manager/mkdir", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            target_address: targetAddr,
            remote_path: remotePath,
            gateway_id: gwId ? parseInt(gwId, 10) : null
          })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Ordner konnte nicht erstellt werden");
        await loadDeviceFiles();
      } catch (e) {
        alert("Fehler: " + e.message);
      }
    });
  }

  if (formatBtn) {
    formatBtn.addEventListener("click", async () => {
      const targetAddr = document.getElementById("openknxFileTargetAddress")?.value.trim();
      const gwId = document.getElementById("openknxFileGatewaySelect")?.value;
      if (!targetAddr) {
        alert("Bitte gib zuerst die Zieladresse (KNX PA) an.");
        return;
      }
      if (!confirm(t("openknx.files.confirmFormat"))) return;

      try {
        const res = await fetch("/api/v1/openknx/file-manager/format", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            target_address: targetAddr,
            remote_path: "/",
            gateway_id: gwId ? parseInt(gwId, 10) : null
          })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Formatierung fehlgeschlagen");
        alert("Dateisystem erfolgreich formatiert!");
        await loadDeviceFiles();
      } catch (e) {
        alert("Fehler beim Formatieren: " + e.message);
      }
    });
  }
}

async function loadDeviceFiles() {
  const targetAddr = document.getElementById("openknxFileTargetAddress")?.value.trim();
  const path = document.getElementById("openknxFilePath")?.value.trim() || "/";
  const gwId = document.getElementById("openknxFileGatewaySelect")?.value;
  const tbody = document.getElementById("openknxFilesTbody");
  const statusBox = document.getElementById("openknxFileStatus");

  if (!targetAddr) {
    alert("Bitte gib eine Zieladresse (z. B. 1.1.25) an.");
    return;
  }

  if (statusBox) {
    statusBox.style.display = "block";
    statusBox.style.color = "#38bdf8";
    statusBox.textContent = `Lese Dateien auf ${targetAddr}:${path} über KNX-Bus aus...`;
  }

  try {
    const res = await fetch("/api/v1/openknx/file-manager/list", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        target_address: targetAddr,
        remote_path: path,
        gateway_id: gwId ? parseInt(gwId, 10) : null
      })
    });
    const items = await res.json();
    if (!res.ok) throw new Error(items.detail || "Verzeichnisabfrage fehlgeschlagen");

    if (statusBox) statusBox.style.display = "none";

    if (!items || items.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="5" style="text-align: center; padding: 2.5rem; color: #94a3b8;">
            ${t("openknx.files.emptyDir")}
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = items.map(item => {
      const isFile = item.is_file;
      const isBin = item.name.endsWith(".bin");
      return `
        <tr>
          <td style="text-align: center; font-size: 1.1rem;">
            ${isFile ? (isBin ? '⚡' : '📄') : '📁'}
          </td>
          <td>
            <div style="font-weight: 500; color: #f8fafc;">${escapeHtml(item.name)}</div>
          </td>
          <td>
            <span style="font-family: monospace; color: #94a3b8;">${isFile ? formatBytes(item.size) : '-'}</span>
          </td>
          <td>
            <code style="font-family: monospace; color: #38bdf8; font-size: 0.8rem;">${escapeHtml(item.path)}</code>
          </td>
          <td style="text-align: right;">
            <div style="display: inline-flex; gap: 0.35rem;">
              ${isFile ? `
                <a href="/api/v1/openknx/file-manager/download?target_address=${encodeURIComponent(targetAddr)}&remote_path=${encodeURIComponent(item.path)}${gwId ? '&gateway_id=' + gwId : ''}" class="btn btn-sm btn-secondary" title="Herunterladen">
                  ⬇️
                </a>
              ` : ''}
              <button type="button" class="btn btn-sm btn-ghost delete-file-btn" data-path="${escapeHtml(item.path)}" style="color: #ef4444;" title="Löschen">
                🗑️
              </button>
              ${isBin ? `
                <button type="button" class="btn btn-sm btn-primary flash-file-btn" data-path="${escapeHtml(item.path)}" title="Direkt als Firmware flashen">
                  ⚡ Flash
                </button>
              ` : ''}
            </div>
          </td>
        </tr>
      `;
    }).join("");

    // Delete listeners
    tbody.querySelectorAll(".delete-file-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const filePath = btn.dataset.path;
        if (!confirm(t("openknx.files.confirmDelete", { path: filePath }))) return;
        try {
          const res = await fetch("/api/v1/openknx/file-manager/delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              target_address: targetAddr,
              remote_path: filePath,
              gateway_id: gwId ? parseInt(gwId, 10) : null
            })
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || "Löschen fehlgeschlagen");
          await loadDeviceFiles();
        } catch (e) {
          alert("Fehler beim Löschen: " + e.message);
        }
      });
    });

  } catch (err) {
    if (statusBox) {
      statusBox.style.color = "#ef4444";
      statusBox.textContent = "❌ Fehler: " + err.message;
    }
  }
}

// ==============================================================================
// TAB 4: Firmware Flasher & OTA
// ==============================================================================
function setupFlashTab() {
  const methodRadios = document.querySelectorAll("input[name='openknxFlashMethod']");
  const sourceRadios = document.querySelectorAll("input[name='openknxFlashSource']");
  const otaFields = document.getElementById("openknxFlashOtaFields");
  const busFields = document.getElementById("openknxFlashBusFields");
  const releaseWrap = document.getElementById("openknxFlashReleaseSelectWrap");
  const fileWrap = document.getElementById("openknxFlashFileUploadWrap");
  const repoSelect = document.getElementById("openknxFlashRepoSelect");
  const tagSelect = document.getElementById("openknxFlashTagSelect");
  const startBtn = document.getElementById("openknxStartFlashBtn");

  // Method toggle
  methodRadios.forEach(radio => {
    radio.addEventListener("change", () => {
      if (radio.value === "ota") {
        if (otaFields) otaFields.style.display = "grid";
        if (busFields) busFields.style.display = "none";
      } else {
        if (otaFields) otaFields.style.display = "none";
        if (busFields) busFields.style.display = "grid";
      }
    });
  });

  // Source toggle
  sourceRadios.forEach(radio => {
    radio.addEventListener("change", () => {
      if (radio.value === "release") {
        if (releaseWrap) releaseWrap.style.display = "flex";
        if (fileWrap) fileWrap.style.display = "none";
      } else {
        if (releaseWrap) releaseWrap.style.display = "none";
        if (fileWrap) fileWrap.style.display = "block";
      }
    });
  });

  // Repo change updates tags
  if (repoSelect) {
    repoSelect.addEventListener("change", () => {
      updateFlashTags();
    });
  }

  // Tag change updates assets
  if (tagSelect) {
    tagSelect.addEventListener("change", () => {
      updateFlashAssets();
    });
  }

  // Start Flash
  if (startBtn) {
    startBtn.addEventListener("click", () => startFirmwareFlash());
  }
}

function populateFlashRepos() {
  const repoSelect = document.getElementById("openknxFlashRepoSelect");
  if (!repoSelect) return;

  const repos = Object.keys(openknxState.releases || {});
  if (repos.length === 0) {
    repoSelect.innerHTML = `<option value="">Keine Repositories geladen</option>`;
    return;
  }

  repoSelect.innerHTML = repos.map(r => `<option value="${escapeHtml(r)}">${escapeHtml(r)}</option>`).join("");
  updateFlashTags();
}

function updateFlashTags() {
  const repoSelect = document.getElementById("openknxFlashRepoSelect");
  const tagSelect = document.getElementById("openknxFlashTagSelect");
  if (!repoSelect || !tagSelect) return;

  const repoName = repoSelect.value;
  const repoData = openknxState.releases[repoName];
  const releases = repoData?.releases || [];

  if (releases.length === 0) {
    tagSelect.innerHTML = `<option value="">Keine Releases</option>`;
    updateFlashAssets();
    return;
  }

  tagSelect.innerHTML = releases.map(r => `
    <option value="${escapeHtml(r.tag_name)}">${escapeHtml(r.tag_name)} ${r.prerelease ? '(Beta)' : '(Stable)'}</option>
  `).join("");

  updateFlashAssets();
}

function updateFlashAssets() {
  const repoSelect = document.getElementById("openknxFlashRepoSelect");
  const tagSelect = document.getElementById("openknxFlashTagSelect");
  const assetSelect = document.getElementById("openknxFlashAssetSelect");
  if (!repoSelect || !tagSelect || !assetSelect) return;

  const repoName = repoSelect.value;
  const tagName = tagSelect.value;
  const repoData = openknxState.releases[repoName];
  const rel = (repoData?.releases || []).find(r => r.tag_name === tagName);
  const assets = (rel?.assets || []).filter(a => a.name.endsWith(".bin") || a.name.endsWith(".hex"));

  if (assets.length === 0) {
    assetSelect.innerHTML = `<option value="">Keine Firmware-Binaries (.bin) im Release gefunden</option>`;
    return;
  }

  assetSelect.innerHTML = assets.map(a => `
    <option value="${escapeHtml(a.name)}">${escapeHtml(a.name)} (${formatBytes(a.size)})</option>
  `).join("");
}

async function startFirmwareFlash() {
  const method = document.querySelector("input[name='openknxFlashMethod']:checked")?.value || "ota";
  const source = document.querySelector("input[name='openknxFlashSource']:checked")?.value || "release";
  const startBtn = document.getElementById("openknxStartFlashBtn");
  const progBar = document.getElementById("openknxFlashProgressBar");
  const progPct = document.getElementById("openknxFlashPercent");
  const statusText = document.getElementById("openknxFlashStatusText");
  const logsEl = document.getElementById("openknxFlashLogs");

  const payload = {
    method: method
  };

  if (method === "ota") {
    payload.ip = document.getElementById("openknxFlashIp")?.value.trim();
    payload.port = parseInt(document.getElementById("openknxFlashPort")?.value || "3232", 10);
    if (!payload.ip) {
      alert("Bitte gib die Ziel-IP für das OTA-Flashing an.");
      return;
    }
  } else {
    payload.target_address = document.getElementById("openknxFlashKnxAddress")?.value.trim();
    const gwId = document.getElementById("openknxFlashGatewaySelect")?.value;
    if (gwId) payload.gateway_id = parseInt(gwId, 10);
    if (!payload.target_address) {
      alert("Bitte gib die physikalische KNX-Adresse des Zielgeräts an.");
      return;
    }
  }

  if (source === "release") {
    payload.repository = document.getElementById("openknxFlashRepoSelect")?.value;
    payload.tag = document.getElementById("openknxFlashTagSelect")?.value;
    payload.asset_name = document.getElementById("openknxFlashAssetSelect")?.value;
    if (!payload.repository || !payload.tag || !payload.asset_name) {
      alert("Bitte wähle ein Release und eine Firmware-Datei (.bin) aus.");
      return;
    }
  } else {
    alert("Lokaler File-Upload für Flash wird vorbereitet: Wähle vorerst ein GitHub-Release.");
    return;
  }

  startBtn.disabled = true;
  progBar.style.width = "0%";
  progPct.textContent = "0%";
  statusText.textContent = "Starte Flash-Vorgang...";
  logsEl.textContent = `[Info] Sende Flash-Auftrag via ${method.toUpperCase()}...\n`;

  try {
    const res = await fetch("/api/v1/openknx/flash", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Flash-Start fehlgeschlagen");

    const taskId = data.task_id;
    openknxState.activeFlashTaskId = taskId;

    // Start polling task
    if (openknxState.flashPollInterval) clearInterval(openknxState.flashPollInterval);
    openknxState.flashPollInterval = setInterval(async () => {
      try {
        const tRes = await fetch(`/api/v1/openknx/tasks/${taskId}`);
        const task = await tRes.json();
        if (!tRes.ok) return;

        progBar.style.width = `${task.progress}%`;
        progPct.textContent = `${task.progress}%`;
        statusText.textContent = task.message || task.status;

        if (task.logs && task.logs.length > 0) {
          logsEl.textContent = task.logs.join("\n");
          logsEl.scrollTop = logsEl.scrollHeight;
        }

        if (task.status === "finished") {
          clearInterval(openknxState.flashPollInterval);
          startBtn.disabled = false;
          statusText.textContent = "✅ Firmware erfolgreich geflasht!";
          progBar.style.background = "#10b981";
        } else if (task.status === "error" || task.status === "cancelled") {
          clearInterval(openknxState.flashPollInterval);
          startBtn.disabled = false;
          statusText.textContent = "❌ Flash-Vorgang abgebrochen oder fehlgeschlagen.";
          progBar.style.background = "#ef4444";
        }
      } catch (_) {}
    }, 500);

  } catch (err) {
    startBtn.disabled = false;
    statusText.textContent = "❌ " + err.message;
    logsEl.textContent += `[Fehler] ${err.message}\n`;
  }
}

// ==============================================================================
// TAB 5: KNXnet/IP Gateways
// ==============================================================================
function setupGatewaysTab() {
  const discoverBtn = document.getElementById("openknxDiscoverGatewaysBtn");
  const toggleAddBtn = document.getElementById("openknxToggleAddGatewayBtn");
  const cancelAddBtn = document.getElementById("openknxCancelAddGwBtn");
  const saveBtn = document.getElementById("openknxSaveGatewayBtn");
  const formWrap = document.getElementById("openknxAddGatewayFormWrap");

  if (toggleAddBtn && formWrap) {
    toggleAddBtn.addEventListener("click", () => {
      formWrap.style.display = formWrap.style.display === "none" ? "block" : "none";
    });
  }

  if (cancelAddBtn && formWrap) {
    cancelAddBtn.addEventListener("click", () => {
      formWrap.style.display = "none";
    });
  }

  if (discoverBtn) {
    discoverBtn.addEventListener("click", async () => {
      discoverBtn.disabled = true;
      const statusEl = document.getElementById("openknxGatewaysStatus");
      if (statusEl) statusEl.textContent = t("openknx.gateways.discovering");

      try {
        const res = await fetch("/api/v1/openknx/gateways/discover?timeout=2.0", { method: "POST" });
        const data = await res.json();
        const found = data.gateways || [];
        if (statusEl) statusEl.textContent = `${found.length} Gateway(s) im Netzwerk gefunden!`;

        for (const gw of found) {
          // Check if already registered
          const exists = openknxState.gateways.some(g => g.host === gw.ip);
          if (!exists) {
            await fetch("/api/v1/openknx/gateways", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                name: gw.name || "KNX IP Gateway",
                host: gw.ip,
                port: gw.port || 3671,
                protocol: "tunneling",
                individual_address: "15.15.250",
                is_default: openknxState.gateways.length === 0
              })
            });
          }
        }
        await loadGateways();
      } catch (e) {
        if (statusEl) statusEl.textContent = "Fehler: " + e.message;
      } finally {
        discoverBtn.disabled = false;
      }
    });
  }

  if (saveBtn) {
    saveBtn.addEventListener("click", async () => {
      const name = document.getElementById("openknxGwName")?.value.trim();
      const host = document.getElementById("openknxGwHost")?.value.trim();
      const port = parseInt(document.getElementById("openknxGwPort")?.value || "3671", 10);
      const protocol = document.getElementById("openknxGwProtocol")?.value || "tunneling";
      const individual_address = document.getElementById("openknxGwAddress")?.value.trim() || "15.15.250";
      const is_default = document.getElementById("openknxGwDefault")?.checked || false;

      if (!name || !host) {
        alert("Bitte Bezeichnung und Host / IP angeben.");
        return;
      }

      try {
        const res = await fetch("/api/v1/openknx/gateways", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, host, port, protocol, individual_address, is_default })
        });
        if (!res.ok) throw new Error("Fehler beim Speichern");
        if (formWrap) formWrap.style.display = "none";
        await loadGateways();
      } catch (e) {
        alert("Fehler: " + e.message);
      }
    });
  }
}

async function loadGateways() {
  try {
    const res = await fetch("/api/v1/openknx/gateways");
    const gateways = await res.json();
    openknxState.gateways = gateways;

    // Update Gateway selects in other tabs
    const selects = [
      document.getElementById("openknxDeviceGatewaySelect"),
      document.getElementById("openknxFileGatewaySelect"),
      document.getElementById("openknxFlashGatewaySelect")
    ];

    selects.forEach(sel => {
      if (!sel) return;
      sel.innerHTML = gateways.map(g => `
        <option value="${g.id}" ${g.is_default ? 'selected' : ''}>${escapeHtml(g.name)} (${escapeHtml(g.host)})</option>
      `).join("");
    });

    // Update active badge in header
    const defaultGw = gateways.find(g => g.is_default) || gateways[0];
    const headerBadge = document.getElementById("openknxActiveGatewayBadge");
    if (headerBadge) {
      if (defaultGw) {
        headerBadge.textContent = `Gateway: ${defaultGw.name} (${defaultGw.host})`;
      } else {
        headerBadge.textContent = `Gateway: Kein Profil hinterlegt`;
      }
    }

    // Render table
    const tbody = document.getElementById("openknxGatewaysTbody");
    if (!tbody) return;

    if (gateways.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6" style="text-align: center; padding: 2.5rem; color: #94a3b8;">
            ${t("openknx.gateways.noGateways")}
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = gateways.map(g => `
      <tr>
        <td style="font-weight: 600; color: #f8fafc;">${escapeHtml(g.name)}</td>
        <td><code style="font-family: monospace; color: #38bdf8;">${escapeHtml(g.host)}:${g.port}</code></td>
        <td><span class="badge" style="background: rgba(255,255,255,0.06); text-transform: uppercase;">${escapeHtml(g.protocol)}</span></td>
        <td><code style="font-family: monospace;">${escapeHtml(g.individual_address || '-')}</code></td>
        <td>
          ${g.is_default ? `
            <span class="badge badge-uptodate">⭐ Standard</span>
          ` : `
            <span style="color: #64748b;">-</span>
          `}
        </td>
        <td style="text-align: right;">
          <button type="button" class="btn btn-sm btn-ghost del-gw-btn" data-id="${g.id}" style="color: #ef4444;" title="Löschen">
            🗑️
          </button>
        </td>
      </tr>
    `).join("");

    tbody.querySelectorAll(".del-gw-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const id = btn.dataset.id;
        if (!confirm("Gateway wirklich löschen?")) return;
        try {
          await fetch(`/api/v1/openknx/gateways/${id}`, { method: "DELETE" });
          await loadGateways();
        } catch (e) {
          alert("Fehler: " + e.message);
        }
      });
    });

  } catch (err) {
    console.error("Fehler beim Laden der Gateways:", err);
  }
}

// ==============================================================================
// TAB 6: .knxprod Generator
// ==============================================================================
function setupKnxprodTab() {
  const dropzone = document.getElementById("openknxXmlDropzone");
  const fileInput = document.getElementById("openknxXmlFileInput");
  const generateBtn = document.getElementById("openknxGenerateKnxprodBtn");

  if (dropzone && fileInput) {
    dropzone.addEventListener("click", () => fileInput.click());

    dropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });

    dropzone.addEventListener("dragleave", () => {
      dropzone.classList.remove("dragover");
    });

    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleXmlFileSelect(e.dataTransfer.files[0]);
      }
    });

    fileInput.addEventListener("change", () => {
      if (fileInput.files && fileInput.files.length > 0) {
        handleXmlFileSelect(fileInput.files[0]);
      }
    });
  }

  if (generateBtn) {
    generateBtn.addEventListener("click", async () => {
      if (!openknxState.selectedXmlFile) {
        alert("Bitte wähle zuerst eine OpenKNX XML-Datei aus.");
        return;
      }

      const mfgId = document.getElementById("openknxXmlMfgId")?.value.trim() || "M-00FA";
      const statusBox = document.getElementById("openknxKnxprodStatus");

      generateBtn.disabled = true;
      generateBtn.textContent = "⏳ Generiere .knxprod...";
      if (statusBox) {
        statusBox.style.display = "block";
        statusBox.innerHTML = `
          <div style="background: rgba(56, 189, 248, 0.1); border: 1px solid rgba(56, 189, 248, 0.3); padding: 0.75rem 1rem; border-radius: 8px; color: #38bdf8;">
            Erzeuge ETS-Archive, knx_master.xml und berechne Signaturen...
          </div>
        `;
      }

      const formData = new FormData();
      formData.append("xml_file", openknxState.selectedXmlFile);
      formData.append("manufacturer_id", mfgId);

      try {
        const res = await fetch("/api/v1/openknx/knxprod/generate", {
          method: "POST",
          body: formData
        });
        if (!res.ok) throw new Error("Generierung fehlgeschlagen");

        const blob = await res.blob();
        const baseName = openknxState.selectedXmlFile.name.replace(/\.[^/.]+$/, "");
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${baseName}.knxprod`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        if (statusBox) {
          statusBox.innerHTML = `
            <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); padding: 0.75rem 1rem; border-radius: 8px; color: #10b981;">
              ✅ .knxprod-Paket erfolgreich generiert und Download gestartet!
            </div>
          `;
        }
      } catch (e) {
        if (statusBox) {
          statusBox.innerHTML = `
            <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); padding: 0.75rem 1rem; border-radius: 8px; color: #ef4444;">
              ❌ Fehler: ${escapeHtml(e.message)}
            </div>
          `;
        }
      } finally {
        generateBtn.disabled = false;
        generateBtn.textContent = "📦 .knxprod generieren & herunterladen";
      }
    });
  }
}

function handleXmlFileSelect(file) {
  openknxState.selectedXmlFile = file;
  const label = document.getElementById("openknxXmlFilename");
  if (label) {
    label.textContent = `Ausgewählt: ${file.name} (${formatBytes(file.size)})`;
    label.style.color = "#38bdf8";
  }
}

// ==============================================================================
// TAB 7: Tasks & Activities Monitor
// ==============================================================================
function setupTasksTab() {
  const refreshBtn = document.getElementById("openknxRefreshTasksBtn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => loadTasks());
  }
}

function startTaskPolling() {
  if (openknxState.taskPollInterval) return;
  openknxState.taskPollInterval = setInterval(() => {
    const autoRefresh = document.getElementById("openknxAutoRefreshTasks")?.checked;
    if (autoRefresh && openknxState.currentTab === "tasks") {
      loadTasks();
    }
  }, 3000);
}

function stopTaskPolling() {
  if (openknxState.taskPollInterval) {
    clearInterval(openknxState.taskPollInterval);
    openknxState.taskPollInterval = null;
  }
}

async function loadTasks() {
  const tbody = document.getElementById("openknxTasksTbody");
  if (!tbody) return;

  try {
    const res = await fetch("/api/v1/openknx/tasks");
    const tasks = await res.json();
    openknxState.tasks = tasks;

    if (!tasks || tasks.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6" style="text-align: center; padding: 2.5rem; color: #94a3b8;">
            ${t("openknx.tasks.noTasks")}
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = tasks.map(tk => {
      const isRunning = tk.status === "running";
      const isSuccess = tk.status === "finished";
      const isError = tk.status === "error";

      let statusBadge = `<span class="badge" style="background: rgba(255,255,255,0.06);">${escapeHtml(tk.status)}</span>`;
      if (isRunning) statusBadge = `<span class="badge" style="background: rgba(56, 189, 248, 0.2); color: #38bdf8;">⏳ Läuft</span>`;
      if (isSuccess) statusBadge = `<span class="badge badge-uptodate">✅ Fertig</span>`;
      if (isError) statusBadge = `<span class="badge" style="background: rgba(239, 68, 68, 0.2); color: #ef4444;">❌ Fehler</span>`;

      return `
        <tr>
          <td><code style="font-family: monospace; color: #94a3b8; font-size: 0.8rem;">${escapeHtml(tk.task_id)}</code></td>
          <td><span class="badge" style="background: rgba(255,255,255,0.06);">${escapeHtml(tk.task_type)}</span></td>
          <td style="font-weight: 500; color: #f8fafc;">${escapeHtml(tk.name)}</td>
          <td>${statusBadge}</td>
          <td style="min-width: 140px;">
            <div style="display: flex; align-items: center; gap: 0.5rem;">
              <div style="flex: 1; height: 8px; background: rgba(15,23,42,0.8); border: 1px solid rgba(255,255,255,0.1); border-radius: 4px; overflow: hidden;">
                <div style="width: ${tk.progress}%; height: 100%; background: ${isError ? '#ef4444' : (isSuccess ? '#10b981' : '#38bdf8')};"></div>
              </div>
              <span style="font-size: 0.75rem; font-family: monospace; color: #94a3b8;">${tk.progress}%</span>
            </div>
          </td>
          <td style="text-align: right;">
            ${isRunning ? `
              <button type="button" class="btn btn-sm btn-ghost cancel-task-btn" data-id="${escapeHtml(tk.task_id)}" style="color: #ef4444;" title="Abbrechen">
                ✕ Abbrechen
              </button>
            ` : '-'}
          </td>
        </tr>
      `;
    }).join("");

    tbody.querySelectorAll(".cancel-task-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const id = btn.dataset.id;
        try {
          await fetch(`/api/v1/openknx/tasks/${id}/cancel`, { method: "POST" });
          await loadTasks();
        } catch (e) {
          alert("Fehler beim Abbrechen: " + e.message);
        }
      });
    });

  } catch (err) {
    console.error("Fehler beim Laden der Tasks:", err);
  }
}

// Auto-init on DOMContentLoaded
if (typeof document !== "undefined") {
  window.addEventListener("konfix:langchange", () => {
    if (typeof I18n !== "undefined" && typeof I18n.applyTranslations === "function") {
      I18n.applyTranslations();
    }
    if (openknxState.currentTab === "releases") {
      renderReleasesGrid();
    } else if (openknxState.currentTab === "devices") {
      loadDevices();
    }
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => initOpenKnxToolbox());
  } else {
    initOpenKnxToolbox();
  }
}
