document.addEventListener("DOMContentLoaded", () => {
  const runBtn = document.getElementById("runMigrationBtn");
  const logBox = document.getElementById("migLogOutput");
  const statusBadge = document.getElementById("migStatusBadge");
  const adminKeyBox = document.getElementById("adminKeyBox");
  const adminKeyInput = document.getElementById("migAdminKey");

  function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  }

  async function loadStatus() {
    try {
      const res = await fetch("/api/v1/admin/migration-status");
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        logBox.style.display = "block";
        logBox.textContent = `🔒 ${err.detail || "Migrationsseite ist deaktiviert."}`;
        runBtn.disabled = true;
        if (statusBadge) {
          statusBadge.textContent = "🔒 Gesperrt (ENABLE_DB_MIGRATION=false)";
          statusBadge.classList.add("locked");
        }
        return;
      }
      const data = await res.json();

      if (data.admin_key_required && adminKeyBox) {
        adminKeyBox.style.display = "block";
      }

      const fallbackBanner = document.getElementById("fallbackBanner");
      if (fallbackBanner) {
        fallbackBanner.style.display = data.fallback_active ? "block" : "none";
      }

      const src = data.source_sqlite || {};
      setText("srcExistsBadge", src.exists ? "✓ Gefunden" : "Nicht vorhanden");
      setText("srcPath", src.path ? src.path.split("/").slice(-2).join("/") : "-");
      setText("srcSize", src.exists ? `${src.size_mb} MB` : "0 MB");
      setText("srcDevices", `${src.manufacturers_count || 0} / ${src.devices_count || 0}`);
      setText("srcEntities", `${src.com_objects_count || 0} / ${src.parameters_count || 0}`);
      setText("srcTranslations", `${src.translations_count || 0}`);
      setText("srcYamlFiles", `${data.yaml_files_count || 0} Dateien`);

      const tgt = data.target_db || {};
      setText("tgtConnBadge", tgt.connected ? "✓ Verbunden" : `⚠️ Nicht verbunden`);
      setText("tgtEngine", tgt.engine || "-");
      setText("tgtUrl", tgt.masked_url || "-");
      setText("tgtDevices", `${tgt.manufacturers_count || 0} / ${tgt.devices_count || 0}`);
      setText("tgtEntities", `${tgt.com_objects_count || 0} / ${tgt.parameters_count || 0}`);
      setText("tgtTranslations", `${tgt.translations_count || 0}`);

      const tgtHintBox = document.getElementById("tgtHintBox");
      if (tgtHintBox) {
        if (!tgt.connected && (tgt.error || tgt.hint)) {
          tgtHintBox.style.display = "block";
          tgtHintBox.innerHTML = `<strong>⚠️ Verbindungsfehler:</strong> ${tgt.error || ""}${tgt.hint ? `<br><br>💡 <em>${tgt.hint}</em>` : ""}`;
        } else {
          tgtHintBox.style.display = "none";
        }
      }

      if (!tgt.connected && tgt.is_external_sql) {
        runBtn.disabled = true;
        runBtn.title = "Ziel-Datenbank ist nicht erreichbar. Bitte Zugangsdaten in .env prüfen.";
      } else {
        runBtn.disabled = false;
        runBtn.title = "";
      }
    } catch (e) {
      logBox.style.display = "block";
      logBox.textContent = `Fehler beim Laden des Status: ${e.message}`;
    }
  }

  if (runBtn) {
    runBtn.addEventListener("click", async () => {
      runBtn.disabled = true;
      const originalText = runBtn.textContent;
      runBtn.textContent = "⏳ Migration läuft... bitte warten";
      logBox.style.display = "block";
      logBox.textContent = "Starte Datenbank-Migration...\n";

      const payload = {
        migrate_from_sqlite: Boolean(document.getElementById("optMigrateSqlite")?.checked),
        sync_relational_and_counts: Boolean(document.getElementById("optSyncCounts")?.checked),
        import_yaml_files: Boolean(document.getElementById("optImportYaml")?.checked),
        vacuum_sqlite: Boolean(document.getElementById("optVacuumSqlite")?.checked),
        disable_flag_after_success: Boolean(document.getElementById("optDisableFlag")?.checked),
        admin_key: adminKeyInput ? adminKeyInput.value.trim() || null : null,
      };

      try {
        const res = await fetch("/api/v1/admin/migrate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          logBox.textContent += `\n❌ Fehler (${res.status}): ${data.detail || res.statusText}`;
          runBtn.disabled = false;
          runBtn.textContent = originalText;
          return;
        }

        if (Array.isArray(data.logs)) {
          logBox.textContent = data.logs.join("\n");
        }

        if (data.target_db) {
          const tgt = data.target_db;
          setText("tgtDevices", `${tgt.manufacturers_count || 0} / ${tgt.devices_count || 0}`);
          setText("tgtEntities", `${tgt.com_objects_count || 0} / ${tgt.parameters_count || 0}`);
          setText("tgtTranslations", `${tgt.translations_count || 0}`);
        }

        if (data.env_flag_disabled) {
          if (statusBadge) {
            statusBadge.textContent = "🔒 ENABLE_DB_MIGRATION=false (Gesperrt)";
            statusBadge.classList.add("locked");
          }
          runBtn.textContent = "✅ Migration abgeschlossen & .env gesperrt";
          runBtn.disabled = true;
        } else {
          runBtn.textContent = "✅ Migration abgeschlossen (erneut ausführen)";
          runBtn.disabled = false;
        }
      } catch (err) {
        logBox.textContent += `\n❌ Netzwerkfehler: ${err.message}`;
        runBtn.disabled = false;
        runBtn.textContent = originalText;
      }
    });
  }

  loadStatus();
});
