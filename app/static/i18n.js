// KoNfiX-Catalog i18n Localization Engine (DE / EN)
// 100% Offline-First, Zero external dependencies, Strict CSP compliant ('self')

const I18N_TRANSLATIONS = {
  de: {
    nav: {
      swagger: "Swagger API Doku",
      yamlEditor: "🛠️ YAML-Editor",
      upload: "⚡ .yaml / .knxprod Upload",
      admin: "🔐 Admin",
      adminActive: "🔓 Admin aktiv (Abmelden)"
    },
    hero: {
      tagline: "Offene Online-Datenbank & YAML-Gerätedefinitionen für KNX / KoNfiX",
      stats: {
        devices: "Geräte",
        manufacturers: "Hersteller",
        files: "Dateien",
        catalogSize: "Kataloggröße"
      },
      searchPlaceholder: "Suche nach Bestellnummer (z. B. AKS-0816.04), Name, Applikation...",
      allManufacturers: "Alle Hersteller"
    },
    devTools: {
      openStandard: "📐 Open Standard",
      offlineFirst: "100% Offline-First",
      title: "KoNfiX-YAML Gerätedefinitionen",
      desc: "Erstelle offene, herstellerunabhängige KNX-Gerätedefinitionen lokal auf deinem Computer oder bearbeite sie im interaktiven Web-Editor mit eindeutigem Link und lokalem Auto-Save.",
      jsonSchemaBtn: "JSON-Schema (.json)",
      jsonSchemaTitle: "Offizielles JSON Schema für Autovervollständigung in IDEs",
      templateBtn: "Starter-Vorlage (.yaml)",
      templateTitle: "Kommentierte Starter-Vorlage für eigene Geräte",
      openEditorBtn: "🚀 Web-Editor öffnen",
      resumeDraftLabel: "Entwurf fortsetzen:",
      resumeDraftPlaceholder: "Entwurfs-Code (z. B. DFT-7X9K2M)...",
      resumeDraftBtn: "Laden ➔",
      ideHintLabel: "IDE-Autovervollständigung:"
    },
    results: {
      heading: "Gerätekatalog",
      count: "{count} Einträge"
    },
    devices: {
      loading: "Lade KNX-Katalogdaten...",
      emptyTitle: "🔍 Keine passenden KNX-Geräte gefunden.",
      emptyHint: "Lade eine .knxprod-Datei über den Upload-Button hoch oder passe den Suchbegriff an.",
      error: "❌ Fehler beim Laden der Daten: {message}"
    },
    card: {
      noApp: "Keine Applikation angegeben",
      viewYaml: "📄 YAML ansehen",
      downloadYamlTitle: "KoNfiX-YAML Gerätedefinition herunterladen",
      sourceBadge: "🌐 Hersteller-Quelle",
      sourceBadgeTitle: "Offizieller Hersteller-Download-Link",
      myDevice: "🔑 Mein Gerät",
      myDeviceTitle: "Du besitzt den Bearbeitungscode für dieses Gerät",
      selectBulk: "Auswählen für Sammelaktion",
      editTooltip: "Gerät bearbeiten",
      editCreatorTooltip: "Gerät bearbeiten (Ersteller)",
      deleteTooltip: "Gerät löschen",
      takedownLink: "🏳️ Rechteinhaber? Takedown anfordern",
      takedownSubject: "Takedown-Anfrage: KNX-Gerät {order_number}",
      takedownBody: "Sehr geehrtes KoNfiX-Team,\n\nals Rechteinhaber bitte ich um Löschung / Sperrung des folgenden Eintrags:\nGerät: {name}\nBestellnummer: {order_number}\n\nBegründung:\n",
      restInfo: "💻 REST Info",
      openInEditor: "🛠️ Im Editor öffnen",
      openInEditorTitle: "Im lokalen KoNfiX-YAML Editor bearbeiten"
    },
    uploadModal: {
      title: "⚡ Gerätedefinition bereitstellen",
      tabFile: "📁 Datei-Upload",
      tabUrl: "🌐 Aus Hersteller-Link importieren",
      fileDesc: "Lade native KoNfiX-Gerätedefinitionen (.yaml), ETS-Projekte (.knxproj), .vd5 oder klassische .knxprod / .zip-Dateien hoch. KNX-Dateien werden automatisch vollständig in das offene KoNfiX-YAML-Format konvertiert.",
      sourceUrlLabel: "🔗 Offizielle Hersteller-Download-URL (optional):",
      sourceUrlPlaceholder: "https://hersteller.de/download/produkt.knxprod",
      fileConsent: "Ich bestätige, dass ich berechtigt bin, diese Gerätedatei hochzuladen oder dass es sich um frei bereitgestellte Gerätedefinitionen handelt.",
      dropZoneTitle: ".yaml, .knxprod, .knxproj oder .vd5 hier ablegen",
      dropZoneSub: "oder klicken zum Auswählen (auch mehrere Dateien)",
      urlDesc: "Gib den offiziellen Download-Link des Herstellers an. KoNfiX parst die XML-Metadaten direkt im Speicher und leitet Downloads transparent per HTTP 302 zum Hersteller weiter (100% rechtssicher, kein lokaler Speicherbedarf!).",
      urlInputLabel: "🌐 Hersteller-Download-Link (.knxprod oder .zip):",
      urlInputPlaceholder: "https://www.mdt.de/download/MDT_AKS.knxprod",
      urlCacheCheckbox: "Binärdatei auch auf dem Server cachen (Standard: aus = reines Verlinken)",
      urlConsent: "Ich bestätige, dass es sich um einen offiziellen, öffentlich frei zugänglichen Download des Herstellers handelt.",
      startUrlImportBtn: "⬇️ Von Hersteller-Link importieren & indexieren",
      analyzingText: "Analysiere KNX-XML und importiere Geräte...",
      convertingText: "⚡ Konvertiere XML-Metadaten & erzeuge KoNfiX-YAML...",
      uploadingFile: "Übertrage '{filename}' ({percent}%)...",
      editCodeTitle: "🔑 Dein Bearbeitungscode",
      editCodeBadge: "Gespeichert",
      editCodeDesc: "Wichtig: Speichere diesen Bearbeitungscode gut ab! Nur mit diesem Code (oder als Administrator) kannst du deine importierten Geräte nachträglich bearbeiten, aktualisieren oder überschreiben.",
      copyEditCodeBtn: "📋 Kopieren",
      copiedEditCodeBtn: "✅ Kopiert!",
      restHintTitle: "Tipp für Automatisierung:",
      restHintUrl: "• Per URL importieren:",
      restHintFile: "• Datei-Upload:",
      consentAlert: "Bitte bestätigen Sie vor dem Upload die rechtliche Berechtigung bzw. die freie Verfügbarkeit der Datei.",
      selectFileConsentAlert: "Bitte bestätigen Sie vor der Dateiauswahl das Berechtigungs-Häkchen.",
      urlMissingAlert: "Bitte gib eine gültige Hersteller-Download-URL an (http:// oder https://).",
      devicesIndexed: "{count} Gerät(e) indexiert",
      importError: "Fehler beim Import",
      importSuccessSummary: "Import erfolgreich abgeschlossen! {success} Datei(en) verarbeitet.",
      importCompleted: "Import abgeschlossen: {success} erfolgreich, {failed} Fehler",
      importingUrl: "Lade Datei von {url} herunter und indexiere Metadaten...",
      indexedFromUrlSuccess: "✓ Erfolgreich von Hersteller-Link indexiert!",
      urlManufacturerLabel: "Hersteller:",
      urlDevicesLabel: "Geräte:",
      urlCachedNotice: "Datei wurde lokal gecacht.",
      urlRedirectNotice: "100% rechtssicher: Reines Metadaten-Indexing & Verlinkung.",
      urlImportError: "❌ Fehler beim Import von URL:",
      retryBtn: "Erneut versuchen",
      networkError: "Netzwerkfehler während des Uploads von '{filename}'",
      serverError: "Server-Fehler: Ungültige Antwort (HTTP {status})"
    },
    restModal: {
      title: "Gerätedetails",
      desc: "Diese KoNfiX-Gerätedefinition kann direkt per REST-API automatisiert in Skripte oder CI/CD-Pipelines eingebunden werden.",
      downloadPost: "1. Download per POST (YAML):",
      downloadGet: "2. Download per GET (YAML):",
      downloadRedirect: "3. Download mit Hersteller-Redirect (HTTP 302):",
      officialSource: "Offizielle Hersteller-Quelle:"
    },
    legalModal: {
      title: "Rechtliche Hinweise & Disclaimer",
      sec1Title: "1. Markenzeichen und Kompatibilität (§ 23 MarkenG)",
      sec1Body: "KNX® und das KNX-Logo sind eingetragene Marken der KNX Association cvba, Brüssel. Dieses Projekt („KoNfiX-Database“) ist ein unabhängiges Open-Source-Katalogsystem und steht in keiner geschäftlichen Verbindung, Partnerschaft oder offiziellen Beziehung zur KNX Association cvba oder den gelisteten Herstellern. Die Nennung von Marken, Herstellernamen und Produktbezeichnungen erfolgt ausschließlich zur sachgerechten Identifikation und Interoperabilitätsbestimmung im Sinne von § 23 MarkenG.",
      sec2Title: "2. Zweck und Herkunft der Produktdaten",
      sec2Body: "Die in dieser Datenbank indexierten Metadaten und .knxprod-Dateien dienen der technischen Parametrierung von Gebäudeautomationsanlagen. Sofern eine offizielle Hersteller-URL hinterlegt ist, leitet der Download-Endpunkt bevorzugt direkt auf den originalen CDN/Server des jeweiligen Herstellers weiter.",
      sec3Title: "3. Notice-and-Takedown-Verfahren (Rechteinhaber)",
      sec3Body1: "Sollten Sie Rechteinhaber eines gelisteten Produkts sein und der Bereitstellung oder Verlinkung widersprechen wollen, senden Sie bitte eine formlose Mitteilung an:",
      sec3Body2: "Wir prüfen eingehende Meldungen unverzüglich und entfernen beanstandete Dateien bzw. Einträge innerhalb kürzester Frist („Notice and Takedown“)."
    },
    adminModal: {
      title: "🔐 Admin-Authentifizierung",
      desc: "Gib den Admin API-Key ein, um Geräte zu verwalten, Metadaten anzupassen oder Takedowns durchzuführen.",
      placeholder: "Admin API-Key eingeben...",
      cancelBtn: "Abbrechen",
      submitBtn: "Anmelden",
      emptyKeyError: "Bitte gib ein Admin-Passwort ein.",
      invalidKeyError: "Ungültiger Admin API-Key oder auf dem Server ist kein Admin-Passwort konfiguriert.",
      logoutConfirm: "Admin-Modus beenden und abmelden?"
    },
    editModal: {
      title: "✏️ Gerät bearbeiten",
      orderNumber: "Bestellnummer:",
      name: "Gerätename:",
      sourceUrl: "🌐 Offizielle Hersteller-Download-URL (source_url):",
      sourceUrlPlaceholder: "https://hersteller.de/download/...",
      hwVersion: "Hardware-Version:",
      busCurrent: "Bus-Strom (mA):",
      description: "Beschreibung:",
      editCodeLabel: "🔑 Bearbeitungscode (oder Admin-Key): *",
      editCodePlaceholder: "z. B. 3f9a7c2b... (vom Import/Upload)",
      editCodeHint: "Wird benötigt, wenn du nicht als Administrator eingeloggt bist. Falls du das Gerät in diesem Browser hochgeladen hast, wird der Code automatisch ausgefüllt.",
      cancelBtn: "Abbrechen",
      saveBtn: "Änderungen speichern",
      saving: "Speichere...",
      success: "✅ Gerät erfolgreich aktualisiert!",
      errorCodeRequired: "Bitte gib den Bearbeitungscode oder den Admin-Key ein."
    },
    deleteModal: {
      title: "🗑️ Gerät löschen (Takedown)",
      desc: "Möchtest du das Gerät wirklich aus dem Katalog entfernen?",
      confirmDesc: "Möchtest du das Gerät <strong>{name}</strong> (<code>{order}</code>) wirklich dauerhaft aus dem Katalog entfernen?",
      deleteFileCheckbox: "Zugehörige .knxprod-Datei ebenfalls vom Server löschen",
      cancelBtn: "Abbrechen",
      confirmBtn: "Endgültig löschen",
      deleting: "Lösche...",
      success: "✅ Gerät erfolgreich gelöscht."
    },
    batchDeleteModal: {
      title: "🗑️ Mehrere Geräte löschen (Batch)",
      desc: "Möchtest du die folgenden ausgewählten Geräte wirklich unwiderruflich aus dem Katalog entfernen?",
      confirmDesc: "Möchtest du die folgenden <strong>{count}</strong> ausgewählten Geräte wirklich unwiderruflich aus dem Katalog entfernen?",
      deleteFilesCheckbox: "Zugehörige .knxprod-Dateien ebenfalls vom Server entfernen (falls keine anderen Geräte darauf verweisen)",
      cancelBtn: "Abbrechen",
      confirmBtn: "Ausgewählte endgültig löschen",
      deleting: "Lösche...",
      success: "✅ {count} Geräte erfolgreich gelöscht."
    },
    bulkToolbar: {
      selected: "Geräte ausgewählt",
      selectAll: "Alle sichtbaren wählen",
      deselectAll: "Auswahl aufheben",
      deleteSelected: "🗑️ Ausgewählte löschen"
    },
    yamlModal: {
      title: "📄 KoNfiX-YAML Definition",
      subtitle: "Gerätedefinition",
      copyBtn: "📋 Kopieren",
      copied: "✅ Kopiert!",
      downloadBtn: "⬇️ Herunterladen",
      loading: "Lade YAML...",
      loadingText: "Lade YAML-Definition...",
      errorText: "Fehler beim Laden der YAML-Definition.",
      networkErrorText: "Netzwerkfehler: {message}"
    },
    editorModal: {
      title: "🛠️ KoNfiX-YAML Editor",
      sandboxBadge: "🔒 Lokale Sandbox (Offline-First)",
      autoSaved: "Automatisch lokal gespeichert",
      templateLabel: "Vorlage:",
      templates: {
        switch: "⚡ Schaltaktor (4-fach)",
        dimmer: "💡 Dimmaktor (2-fach)",
        shutter: "🪟 Jalousieaktor (4-fach)",
        hvac: "🌡️ Raumtemperaturregler",
        binary_input: "🔌 Binäreingang (4-fach)",
        blank: "📄 Leeres Template"
      },
      openBtn: "📂 Öffnen",
      copyBtn: "📋 Kopieren",
      copied: "✅ Kopiert!",
      downloadBtn: "⬇️ YAML Download",
      localDraftLabel: "💾 Lokaler Entwurf:",
      newDraftBtn: "➕ Neuer Entwurf",
      newDraftTitle: "Neuen leeren Entwurf anlegen",
      deleteDraftTitle: "Diesen Entwurf löschen",
      draftLinkBtn: "🔗 Entwurf-Link",
      draftLinkTitle: "Dauerhaften Link zu diesem lokalen Entwurf kopieren",
      portableLinkBtn: "🌐 Portabler Link",
      portableLinkTitle: "Teilbaren Link mit allen Daten in der URL erzeugen",
      publishBtn: "🚀 In Katalog veröffentlichen",
      tabGeneral: "🏢 Allgemein & Hardware",
      tabObjects: "📡 KOs",
      tabParams: "⚙️ Parameter",
      mfgNameLabel: "Hersteller-Name *",
      mfgNamePlaceholder: "z. B. MDT technologies",
      mfgCodeLabel: "Hersteller-Code (Slug, lowercase) *",
      mfgCodePlaceholder: "z. B. mdt",
      orderNumberLabel: "Bestellnummer *",
      orderNumberPlaceholder: "z. B. AKS-0816.04",
      devNameLabel: "Gerätename *",
      devNamePlaceholder: "z. B. Schaltaktor 8-fach 16A",
      descLabel: "Produktbeschreibung",
      descPlaceholder: "Optionale Beschreibung des Geräts...",
      hwNameLabel: "Hardware-Name",
      hwNamePlaceholder: "z. B. AKS-0816",
      hwVersionLabel: "HW-Version",
      busCurrentLabel: "Busstrom (mA)",
      appIdLabel: "Applikations-ID (lowercase)",
      appIdPlaceholder: "z. B. mdt_aks-0816_v1",
      appVersionLabel: "Applikations-Version / Maske",
      koHeading: "Kommunikationsobjekte (KOs)",
      koSearchPlaceholder: "🔍 KO suchen (Nr, Name, DPT)...",
      addKoBtn: "➕ Objekt",
      paramHeading: "Geräteparameter & Menüstruktur",
      paramSearchPlaceholder: "🔍 Parameter suchen (ID, Name, Text)...",
      paramAllPages: "Alle Seiten / Menüs",
      addParamBtn: "➕ Parameter",
      validSchema: "✓ Valide (Schema v1)",
      invalidSchema: "⚠️ Validierungsfehler",
      schemaDocLink: "Schema Doku",
      formatBtn: "🔄 Formatieren",
      deleteDraftConfirm: "Entwurf '{code}' wirklich unwiderruflich löschen?",
      deleteDraftOnlyOne: "Der einzige verbleibende Entwurf kann nicht gelöscht werden.",
      draftLinkCopied: "🔗 Link zum Entwurf in Zwischenablage kopiert!",
      portableLinkCopied: "🌐 Portabler Link in Zwischenablage kopiert! (Enthält alle Daten)",
      savedDraftDefaultTitle: "Gespeicherter Entwurf",
      newDraftDefaultTitle: "Neuer Entwurf",
      deviceDraftTitle: "Gerät {order}",
      incomplete: "⚠️ Unvollständig",
      valid: "✓ Schema v1 valide",
      syntaxError: "❌ Syntaxfehler",
      missingFields: "Pflichtfelder fehlen: manufacturer.code, manufacturer.name, device.order_number, device.name",
      deleteItem: "Löschen",
      noObjectsFound: "Keine Kommunikationsobjekte gefunden",
      noParamsFound: "Keine Parameter gefunden",
      showingItems: "Zeige {start}–{end} von {total} {label}",
      itemsTotal: "{total} {label}",
      pageOf: "Seite {current} von {total}",
      firstPage: "Erste Seite",
      prevPage: "Zurück",
      nextPage: "Weiter",
      lastPage: "Letzte Seite",
      objectsLabel: "Objekte",
      paramsLabel: "Parameter",
      addCondition: "⚡ Bedingung hinzufügen",
      conditionsHeader: "⚡ Bedingungen (Sichtbarkeit & Aktivierung)",
      clickValues: "Werte anklicken:",
      targetParam: "Ziel-Parameter (param_id)",
      whenValue: "Wenn Wert (when_values)",
      deleteCondTooltip: "Bedingung löschen",
      optionsCount: "Auswahloptionen ({count})",
      noEnumOptions: "⚠️ Keine Optionen definiert für enum",
      koNum: "KO-Nr.",
      koName: "Name / Kanal",
      koFunc: "Funktion",
      koDpt: "DPT (z. B. 1.001)",
      koSize: "Größe (z. B. 1 Bit)",
      paramId: "ID (lowercase)",
      paramName: "Bezeichnung / Text",
      paramType: "Typ",
      paramDefault: "Default-Wert",
      paramPage: "Seite / Menüpfad",
      allPages: "Alle Seiten / Menüs ({count})",
      loadedFromCatalog: "Geladen aus Katalog: {order}{editable}",
      editableWithCode: " (Bearbeitbar mit deinem Code)",
      loadError: "Konnte Gerät nicht in den Editor laden: {error}",
      enterDraftCode: "Bitte gib einen Entwurfscode ein (z. B. DFT-7X9K2M).",
      noYamlData: "Der Editor enthält keine YAML-Daten.",
      invalidYaml: "Ungültiges YAML: {error}",
      orderNumberRequired: "Bitte gib im YAML mindestens eine Bestellnummer unter 'device.order_number' an.",
      consentRequired: "Bitte bestätige die Berechtigung zur Veröffentlichung.",
      copyError: "Fehler beim Kopieren in die Zwischenablage",
      portableLinkError: "Fehler beim Erzeugen des portablen Links",
      linkCopied: "✅ Link kopiert!",
      portableCopied: "✅ Portabler Link kopiert!"
    },
    publishModal: {
      title: "🚀 Im Katalog veröffentlichen",
      desc: "Übertrage deine im Editor erstellte Gerätedefinition direkt in den zentralen KoNfiX-Katalog.",
      deviceLabel: "Gerät:",
      orderNumberLabel: "Bestellnummer:",
      manufacturerLabel: "Hersteller:",
      editCodeLabel: "🔑 Bearbeitungscode (falls Gerät schon im Katalog existiert):",
      editCodePlaceholder: "z. B. a1b2c3d4e5f60718",
      editCodeHint: "Wird für neue Geräte automatisch neu erzeugt oder bei vorhandenen Geräten geprüft.",
      consent: "Ich bestätige, dass die Gerätedefinition korrekt ist und veröffentlicht werden darf.",
      cancelBtn: "Abbrechen",
      publishBtn: "Veröffentlichen",
      publishing: "Veröffentliche Gerätedefinition...",
      success: "✅ Erfolgreich im Katalog veröffentlicht!",
      error: "❌ Fehler bei der Veröffentlichung: {message}"
    },
    footer: {
      copyright: "KoNfiX-Database © 2026 • KNX-kompatibles REST-Katalogsystem (AGPL-3.0)",
      openapi: "OpenAPI Spec",
      jsonApi: "JSON API",
      legalNotice: "Rechtliche Hinweise & Disclaimer",
      github: "GitHub Repository"
    }
  },

  en: {
    nav: {
      swagger: "Swagger API Docs",
      yamlEditor: "🛠️ YAML Editor",
      upload: "⚡ Upload .yaml / .knxprod",
      admin: "🔐 Admin",
      adminActive: "🔓 Admin Active (Logout)"
    },
    hero: {
      tagline: "Open Online Database & YAML Device Definitions for KNX / KoNfiX",
      stats: {
        devices: "Devices",
        manufacturers: "Manufacturers",
        files: "Files",
        catalogSize: "Catalog Size"
      },
      searchPlaceholder: "Search by order number (e.g. AKS-0816.04), name, application...",
      allManufacturers: "All Manufacturers"
    },
    devTools: {
      openStandard: "📐 Open Standard",
      offlineFirst: "100% Offline-First",
      title: "KoNfiX-YAML Device Definitions",
      desc: "Create open, vendor-neutral KNX device definitions locally on your computer or edit them in the interactive web editor with unique links and local auto-save.",
      jsonSchemaBtn: "JSON Schema (.json)",
      jsonSchemaTitle: "Official JSON Schema for IDE autocompletion",
      templateBtn: "Starter Template (.yaml)",
      templateTitle: "Commented starter template for custom devices",
      openEditorBtn: "🚀 Open Web Editor",
      resumeDraftLabel: "Resume draft:",
      resumeDraftPlaceholder: "Draft code (e.g. DFT-7X9K2M)...",
      resumeDraftBtn: "Load ➔",
      ideHintLabel: "IDE Autocompletion:"
    },
    results: {
      heading: "Device Catalog",
      count: "{count} entries"
    },
    devices: {
      loading: "Loading KNX catalog data...",
      emptyTitle: "🔍 No matching KNX devices found.",
      emptyHint: "Upload a .knxprod file using the upload button or adjust your search query.",
      error: "❌ Error loading data: {message}"
    },
    card: {
      noApp: "No application specified",
      viewYaml: "📄 View YAML",
      downloadYamlTitle: "Download KoNfiX-YAML device definition",
      sourceBadge: "🌐 Manufacturer Source",
      sourceBadgeTitle: "Official manufacturer download link",
      myDevice: "🔑 My Device",
      myDeviceTitle: "You own the edit code for this device",
      selectBulk: "Select for bulk action",
      editTooltip: "Edit device",
      editCreatorTooltip: "Edit device (creator)",
      deleteTooltip: "Delete device",
      takedownLink: "🏳️ Rights owner? Request takedown",
      takedownSubject: "Takedown Request: KNX Device {order_number}",
      takedownBody: "Dear KoNfiX Team,\n\nAs the rights owner, I request the removal / restriction of the following catalog entry:\nDevice: {name}\nOrder Number: {order_number}\n\nReason:\n",
      restInfo: "💻 REST Info",
      openInEditor: "🛠️ Open in Editor",
      openInEditorTitle: "Edit in local KoNfiX-YAML editor"
    },
    uploadModal: {
      title: "⚡ Provide Device Definition",
      tabFile: "📁 File Upload",
      tabUrl: "🌐 Import from Vendor URL",
      fileDesc: "Upload native KoNfiX device definitions (.yaml), ETS projects (.knxproj), .vd5 or classic .knxprod / .zip files. KNX files are automatically converted into the open KoNfiX-YAML format.",
      sourceUrlLabel: "🔗 Official manufacturer download URL (optional):",
      sourceUrlPlaceholder: "https://vendor.com/download/product.knxprod",
      fileConsent: "I confirm that I am authorized to upload this device file or that it is a freely provided device definition.",
      dropZoneTitle: "Drop .yaml, .knxprod, .knxproj or .vd5 here",
      dropZoneSub: "or click to select (multiple files supported)",
      urlDesc: "Provide the official manufacturer download link. KoNfiX parses XML metadata in memory and transparently redirects downloads via HTTP 302 to the vendor (100% legally compliant, zero local disk storage!).",
      urlInputLabel: "🌐 Manufacturer download link (.knxprod or .zip):",
      urlInputPlaceholder: "https://www.mdt.de/download/MDT_AKS.knxprod",
      urlCacheCheckbox: "Cache binary file on server as well (default: off = redirect only)",
      urlConsent: "I confirm that this is an official, publicly accessible manufacturer download.",
      startUrlImportBtn: "⬇️ Import & index from manufacturer link",
      analyzingText: "Analyzing KNX-XML and importing devices...",
      convertingText: "⚡ Converting XML metadata & generating KoNfiX-YAML...",
      uploadingFile: "Uploading '{filename}' ({percent}%)...",
      editCodeTitle: "🔑 Your Edit Code",
      editCodeBadge: "Saved",
      editCodeDesc: "Important: Save this edit code safely! Only with this code (or as administrator) can you edit, update, or overwrite your imported devices later.",
      copyEditCodeBtn: "📋 Copy",
      copiedEditCodeBtn: "✅ Copied!",
      restHintTitle: "Automation Tip:",
      restHintUrl: "• Import via URL:",
      restHintFile: "• File upload:",
      consentAlert: "Please confirm permission and public availability before uploading.",
      selectFileConsentAlert: "Please confirm permission by ticking the consent box before selecting files.",
      urlMissingAlert: "Please provide a valid manufacturer download URL (http:// or https://).",
      devicesIndexed: "{count} device(s) indexed",
      importError: "Import error",
      importSuccessSummary: "Import completed successfully! {success} file(s) processed.",
      importCompleted: "Import completed: {success} successful, {failed} error(s)",
      importingUrl: "Downloading file from {url} and indexing metadata...",
      indexedFromUrlSuccess: "✓ Successfully indexed from manufacturer link!",
      urlManufacturerLabel: "Manufacturer:",
      urlDevicesLabel: "Devices:",
      urlCachedNotice: "File cached locally.",
      urlRedirectNotice: "100% legally compliant: Pure metadata indexing & redirect.",
      urlImportError: "❌ Error importing from URL:",
      retryBtn: "Try again",
      networkError: "Network error during upload of '{filename}'",
      serverError: "Server error: Invalid response (HTTP {status})"
    },
    restModal: {
      title: "Device Details",
      desc: "This KoNfiX device definition can be integrated directly via REST API into automation scripts or CI/CD pipelines.",
      downloadPost: "1. Download via POST (YAML):",
      downloadGet: "2. Download via GET (YAML):",
      downloadRedirect: "3. Download with manufacturer redirect (HTTP 302):",
      officialSource: "Official Manufacturer Source:"
    },
    legalModal: {
      title: "Legal Notice & Disclaimer",
      sec1Title: "1. Trademarks and Compatibility (§ 23 German Trademark Act)",
      sec1Body: "KNX® and the KNX logo are registered trademarks of the KNX Association cvba, Brussels. This project (\"KoNfiX-Database\") is an independent open-source catalog system and has no commercial relationship, partnership, or official affiliation with the KNX Association cvba or the listed manufacturers. Brand names, manufacturer names, and product designations are used solely for accurate identification and technical interoperability purposes.",
      sec2Title: "2. Purpose and Origin of Product Data",
      sec2Body: "The metadata and .knxprod files indexed in this database serve the technical parameterization of building automation systems. If an official manufacturer URL is available, the download endpoint preferably redirects directly to the original server of the respective manufacturer.",
      sec3Title: "3. Notice and Takedown Procedure (Rights Owners)",
      sec3Body1: "If you are a rights owner of a listed product and wish to object to its provision or linking, please send an informal notification to:",
      sec3Body2: "We review incoming notifications promptly and remove disputed files or entries within the shortest possible timeframe (\"Notice and Takedown\")."
    },
    adminModal: {
      title: "🔐 Admin Authentication",
      desc: "Enter the Admin API key to manage devices, adjust metadata, or process takedowns.",
      placeholder: "Enter Admin API key...",
      cancelBtn: "Cancel",
      submitBtn: "Login",
      emptyKeyError: "Please enter an Admin API key.",
      invalidKeyError: "Invalid Admin API key or no admin password is configured on the server.",
      logoutConfirm: "Exit admin mode and log out?"
    },
    editModal: {
      title: "✏️ Edit Device",
      orderNumber: "Order Number:",
      name: "Device Name:",
      sourceUrl: "🌐 Official Manufacturer Download URL (source_url):",
      sourceUrlPlaceholder: "https://vendor.com/download/...",
      hwVersion: "Hardware Version:",
      busCurrent: "Bus Current (mA):",
      description: "Description:",
      editCodeLabel: "🔑 Edit Code (or Admin Key): *",
      editCodePlaceholder: "e.g. 3f9a7c2b... (from import/upload)",
      editCodeHint: "Required if you are not logged in as administrator. If you uploaded the device in this browser, the code is auto-filled.",
      cancelBtn: "Cancel",
      saveBtn: "Save Changes",
      saving: "Saving...",
      success: "✅ Device updated successfully!",
      errorCodeRequired: "Please enter the edit code or admin key."
    },
    deleteModal: {
      title: "🗑️ Delete Device (Takedown)",
      desc: "Do you really want to remove this device from the catalog?",
      confirmDesc: "Do you really want to permanently remove device <strong>{name}</strong> (<code>{order}</code>) from the catalog?",
      deleteFileCheckbox: "Also delete associated .knxprod file from server",
      cancelBtn: "Cancel",
      confirmBtn: "Delete Permanently",
      deleting: "Deleting...",
      success: "✅ Device deleted successfully."
    },
    batchDeleteModal: {
      title: "🗑️ Delete Multiple Devices (Batch)",
      desc: "Do you really want to permanently remove the selected devices from the catalog?",
      confirmDesc: "Do you really want to permanently remove the following <strong>{count}</strong> selected devices from the catalog?",
      deleteFilesCheckbox: "Also delete associated .knxprod files from server (if no other devices reference them)",
      cancelBtn: "Cancel",
      confirmBtn: "Delete Selected Permanently",
      deleting: "Deleting...",
      success: "✅ {count} devices deleted successfully."
    },
    bulkToolbar: {
      selected: "devices selected",
      selectAll: "Select all visible",
      deselectAll: "Deselect all",
      deleteSelected: "🗑️ Delete selected"
    },
    yamlModal: {
      title: "📄 KoNfiX-YAML Definition",
      subtitle: "Device Definition",
      copyBtn: "📋 Copy",
      copied: "✅ Copied!",
      downloadBtn: "⬇️ Download",
      loading: "Loading YAML...",
      loadingText: "Loading YAML definition...",
      errorText: "Error loading YAML definition.",
      networkErrorText: "Network error: {message}"
    },
    editorModal: {
      title: "🛠️ KoNfiX-YAML Editor",
      sandboxBadge: "🔒 Local Sandbox (Offline-First)",
      autoSaved: "Auto-saved locally",
      templateLabel: "Template:",
      templates: {
        switch: "⚡ Switch Actuator (4-fold)",
        dimmer: "💡 Dimming Actuator (2-fold)",
        shutter: "🪟 Shutter Actuator (4-fold)",
        hvac: "🌡️ Room Temperature Controller",
        binary_input: "🔌 Binary Input (4-fold)",
        blank: "📄 Blank Template"
      },
      openBtn: "📂 Open",
      copyBtn: "📋 Copy",
      copied: "✅ Copied!",
      downloadBtn: "⬇️ Download YAML",
      localDraftLabel: "💾 Local Draft:",
      newDraftBtn: "➕ New Draft",
      newDraftTitle: "Create new empty draft",
      deleteDraftTitle: "Delete this draft",
      draftLinkBtn: "🔗 Draft Link",
      draftLinkTitle: "Copy persistent link to this local draft",
      portableLinkBtn: "🌐 Portable Link",
      portableLinkTitle: "Generate shareable link with all data encoded in URL",
      publishBtn: "🚀 Publish to Catalog",
      tabGeneral: "🏢 General & Hardware",
      tabObjects: "📡 Com Objects",
      tabParams: "⚙️ Parameters",
      mfgNameLabel: "Manufacturer Name *",
      mfgNamePlaceholder: "e.g. MDT technologies",
      mfgCodeLabel: "Manufacturer Code (Slug, lowercase) *",
      mfgCodePlaceholder: "e.g. mdt",
      orderNumberLabel: "Order Number *",
      orderNumberPlaceholder: "e.g. AKS-0816.04",
      devNameLabel: "Device Name *",
      devNamePlaceholder: "e.g. Switch Actuator 8-fold 16A",
      descLabel: "Product Description",
      descPlaceholder: "Optional device description...",
      hwNameLabel: "Hardware Name",
      hwNamePlaceholder: "e.g. AKS-0816",
      hwVersionLabel: "HW Version",
      busCurrentLabel: "Bus Current (mA)",
      appIdLabel: "Application ID (lowercase)",
      appIdPlaceholder: "e.g. mdt_aks-0816_v1",
      appVersionLabel: "Application Version / Mask",
      koHeading: "Communication Objects (Com Objects)",
      koSearchPlaceholder: "🔍 Search Com Object (No, Name, DPT)...",
      addKoBtn: "➕ Com Object",
      paramHeading: "Device Parameters & Menu Structure",
      paramSearchPlaceholder: "🔍 Search Parameter (ID, Name, Text)...",
      paramAllPages: "All Pages / Menus",
      addParamBtn: "➕ Parameter",
      validSchema: "✓ Valid (Schema v1)",
      invalidSchema: "⚠️ Validation Error",
      schemaDocLink: "Schema Docs",
      formatBtn: "🔄 Format",
      deleteDraftConfirm: "Permanently delete draft '{code}'?",
      deleteDraftOnlyOne: "Cannot delete the only remaining draft.",
      draftLinkCopied: "🔗 Draft link copied to clipboard!",
      portableLinkCopied: "🌐 Portable link copied to clipboard! (Contains all data)",
      savedDraftDefaultTitle: "Saved Draft",
      newDraftDefaultTitle: "New Draft",
      deviceDraftTitle: "Device {order}",
      incomplete: "⚠️ Incomplete",
      valid: "✓ Schema v1 valid",
      syntaxError: "❌ Syntax error",
      missingFields: "Required fields missing: manufacturer.code, manufacturer.name, device.order_number, device.name",
      deleteItem: "Delete",
      noObjectsFound: "No communication objects found",
      noParamsFound: "No parameters found",
      showingItems: "Showing {start}–{end} of {total} {label}",
      itemsTotal: "{total} {label}",
      pageOf: "Page {current} of {total}",
      firstPage: "First page",
      prevPage: "Back",
      nextPage: "Next",
      lastPage: "Last page",
      objectsLabel: "Objects",
      paramsLabel: "Parameters",
      addCondition: "⚡ Add condition",
      conditionsHeader: "⚡ Conditions (Visibility & Activation)",
      clickValues: "Click values:",
      targetParam: "Target Parameter (param_id)",
      whenValue: "When value (when_values)",
      deleteCondTooltip: "Delete condition",
      optionsCount: "Options ({count})",
      noEnumOptions: "⚠️ No options defined for enum",
      koNum: "Obj. No.",
      koName: "Name / Channel",
      koFunc: "Function",
      koDpt: "DPT (e.g. 1.001)",
      koSize: "Size (e.g. 1 Bit)",
      paramId: "ID (lowercase)",
      paramName: "Name / Text",
      paramType: "Type",
      paramDefault: "Default Value",
      paramPage: "Page / Menu Path",
      allPages: "All Pages / Menus ({count})",
      loadedFromCatalog: "Loaded from catalog: {order}{editable}",
      editableWithCode: " (Editable with your code)",
      loadError: "Could not load device into editor: {error}",
      enterDraftCode: "Please enter a draft code (e.g. DFT-7X9K2M).",
      noYamlData: "The editor contains no YAML data.",
      invalidYaml: "Invalid YAML: {error}",
      orderNumberRequired: "Please specify at least an order number under 'device.order_number' in the YAML.",
      consentRequired: "Please confirm permission to publish.",
      copyError: "Error copying to clipboard",
      portableLinkError: "Error generating portable link",
      linkCopied: "✅ Link copied!",
      portableCopied: "✅ Portable link copied!"
    },
    publishModal: {
      title: "🚀 Publish to Catalog",
      desc: "Publish your device definition created in the editor directly to the central KoNfiX catalog.",
      deviceLabel: "Device:",
      orderNumberLabel: "Order Number:",
      manufacturerLabel: "Manufacturer:",
      editCodeLabel: "🔑 Edit Code (if device already exists in catalog):",
      editCodePlaceholder: "e.g. a1b2c3d4e5f60718",
      editCodeHint: "Auto-generated for new devices or validated for existing devices.",
      consent: "I confirm that the device definition is correct and authorized to be published.",
      cancelBtn: "Cancel",
      publishBtn: "Publish",
      publishing: "Publishing device definition...",
      success: "✅ Successfully published to catalog!",
      error: "❌ Error during publishing: {message}"
    },
    footer: {
      copyright: "KoNfiX-Database © 2026 • KNX-compatible REST catalog system (AGPL-3.0)",
      openapi: "OpenAPI Spec",
      jsonApi: "JSON API",
      legalNotice: "Legal Notice & Disclaimer",
      github: "GitHub Repository"
    }
  }
};

const I18n = {
  currentLang: "de",
  translations: I18N_TRANSLATIONS,

  init() {
    if (typeof window === "undefined" || !window.location) return;
    // 1. Check URL parameter ?lang=
    const params = new URLSearchParams(window.location.search);
    const langParam = params.get("lang");
    if (langParam && (langParam.toLowerCase() === "de" || langParam.toLowerCase() === "en")) {
      this.currentLang = langParam.toLowerCase();
      try {
        localStorage.setItem("konfix_lang", this.currentLang);
      } catch (_) {}
    } else {
      // 2. Check localStorage
      let storedLang = null;
      try {
        storedLang = localStorage.getItem("konfix_lang");
      } catch (_) {}

      if (storedLang && (storedLang === "de" || storedLang === "en")) {
        this.currentLang = storedLang;
      } else {
        // 3. Fallback to browser language
        const navLang = (navigator.language || navigator.userLanguage || "").toLowerCase();
        if (navLang.startsWith("en")) {
          this.currentLang = "en";
        } else {
          this.currentLang = "de";
        }
      }
    }

    this.applyTranslations();
    this.updateLanguageButtons();
    this.bindLanguageSwitcher();
  },

  getLanguage() {
    return this.currentLang;
  },

  setLanguage(lang) {
    if (lang !== "de" && lang !== "en") return;
    if (this.currentLang === lang) return;

    this.currentLang = lang;
    try {
      localStorage.setItem("konfix_lang", lang);
    } catch (_) {}

    document.documentElement.lang = lang;
    this.applyTranslations();
    this.updateLanguageButtons();

    // Dispatch global custom event for dynamic re-renders in app.js
    window.dispatchEvent(new CustomEvent("konfix:langchange", { detail: { lang } }));
  },

  t(key, params = {}) {
    const langDict = I18N_TRANSLATIONS[this.currentLang] || I18N_TRANSLATIONS.de;
    const fallbackDict = I18N_TRANSLATIONS.de;

    const resolveKey = (dict, path) => {
      const parts = path.split(".");
      let cur = dict;
      for (const part of parts) {
        if (!cur || typeof cur !== "object" || !(part in cur)) {
          return null;
        }
        cur = cur[part];
      }
      return typeof cur === "string" ? cur : null;
    };

    let text = resolveKey(langDict, key);
    if (text === null) {
      text = resolveKey(fallbackDict, key) || key;
    }

    // Replace {placeholder} tokens
    if (params && typeof params === "object") {
      for (const [k, v] of Object.entries(params)) {
        text = text.replace(new RegExp(`\\{${k}\\}`, "g"), v != null ? String(v) : "");
      }
    }

    return text;
  },

  applyTranslations(root = document) {
    document.documentElement.lang = this.currentLang;

    // Elements with data-i18n
    const textEls = root.querySelectorAll("[data-i18n]");
    textEls.forEach((el) => {
      const key = el.getAttribute("data-i18n");
      if (key) {
        const translation = this.t(key);
        // If element contains HTML or is intended for text
        if (el.getAttribute("data-i18n-html") === "true") {
          el.innerHTML = translation;
        } else {
          el.textContent = translation;
        }
      }
    });

    // Elements with data-i18n-placeholder
    const placeholderEls = root.querySelectorAll("[data-i18n-placeholder]");
    placeholderEls.forEach((el) => {
      const key = el.getAttribute("data-i18n-placeholder");
      if (key) {
        el.setAttribute("placeholder", this.t(key));
      }
    });

    // Elements with data-i18n-title
    const titleEls = root.querySelectorAll("[data-i18n-title]");
    titleEls.forEach((el) => {
      const key = el.getAttribute("data-i18n-title");
      if (key) {
        el.setAttribute("title", this.t(key));
      }
    });

    // Elements with data-i18n-aria
    const ariaEls = root.querySelectorAll("[data-i18n-aria]");
    ariaEls.forEach((el) => {
      const key = el.getAttribute("data-i18n-aria");
      if (key) {
        el.setAttribute("aria-label", this.t(key));
      }
    });
  },

  updateLanguageButtons() {
    const buttons = document.querySelectorAll(".lang-btn");
    buttons.forEach((btn) => {
      const lang = btn.getAttribute("data-lang");
      if (lang === this.currentLang) {
        btn.classList.add("active");
        btn.setAttribute("aria-pressed", "true");
      } else {
        btn.classList.remove("active");
        btn.setAttribute("aria-pressed", "false");
      }
    });
  },

  bindLanguageSwitcher() {
    const switchContainer = document.getElementById("langSwitch");
    if (!switchContainer) return;

    switchContainer.querySelectorAll(".lang-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const targetLang = btn.getAttribute("data-lang");
        if (targetLang) {
          this.setLanguage(targetLang);
        }
      });
    });
  }
};

// Auto-initialize when DOM is ready
if (typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => I18n.init());
  } else {
    I18n.init();
  }
}

if (typeof window !== "undefined") {
  window.I18n = I18n;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { I18n, I18N_TRANSLATIONS };
}

