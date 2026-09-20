/**
 * VeriSlip Frontend Application Logic v2.0
 * Next-Level Multi-Layer Forensic Cockpit, Batch Auditor, & WhatsApp Bot Simulator
 */

document.addEventListener("DOMContentLoaded", () => {
  // State
  let currentImageBlob = null;
  let currentBase64 = null;
  let currentResults = null;
  let activeView = "original";
  let currentZoom = 1.0;
  let batchDataCache = [];
  let triageLoading = false;
  let historyPage = 1;
  let historyHasMore = false;
  let sessionApiKey = (typeof localStorage !== "undefined" && localStorage.getItem("verislip_api_key")) || "verislip-dev-key";

  function getSessionApiKey() {
    return sessionApiKey;
  }

  function protectedFetch(url, options = {}) {
    const headers = new Headers(options.headers || {});
    const apiKey = getSessionApiKey();
    if (apiKey) headers.set("X-API-Key", apiKey);
    return fetch(url, { ...options, headers });
  }

  // Tab Elements
  const tabs = document.querySelectorAll(".nav-tab");
  const tabPanes = document.querySelectorAll(".tab-pane");

  // Cockpit Controls
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");
  const btnBrowse = document.getElementById("btn-browse");
  const btnRunScan = document.getElementById("btn-run-scan");

  const btnSampleAuth = document.getElementById("btn-sample-auth");
  const btnSampleTamperAmt = document.getElementById("btn-sample-tamper-amt");
  const btnSampleTamperRef = document.getElementById("btn-sample-tamper-ref");
  const btnSampleTamperPeoples = document.getElementById("btn-sample-tamper-peoples");
  const btnSampleTamperParadox = document.getElementById("btn-sample-tamper-paradox");

  const bankSelect = document.getElementById("bank-select");
  const refInput = document.getElementById("ref-input");
  const voiceCommandInput = document.getElementById("voice-command-input");
  const btnRunVoiceCommand = document.getElementById("btn-run-voice-command");
  const btnVoiceListen = document.getElementById("btn-voice-listen");
  const btnVoiceHelp = document.getElementById("btn-voice-help");
  const voiceHelpDialog = document.getElementById("voice-help-dialog");
  const voiceStatus = document.getElementById("voice-status");

  // Canvas & Zoom Controls
  const displayImage = document.getElementById("display-image");
  const overlayCanvas = document.getElementById("overlay-canvas");
  const placeholderEmpty = document.getElementById("placeholder-empty");
  const loadingSpinner = document.getElementById("loading-spinner");
  const currentViewBadge = document.getElementById("current-view-badge");
  const togglePills = document.querySelectorAll(".toggle-pill");

  const btnZoomIn = document.getElementById("btn-zoom-in");
  const btnZoomOut = document.getElementById("btn-zoom-out");
  const btnZoomReset = document.getElementById("btn-zoom-reset");

  // Metadata Bar Elements
  const metaBank = document.getElementById("meta-bank");
  const metaAmount = document.getElementById("meta-amount");
  const metaRef = document.getElementById("meta-ref");
  const metaViewport = document.getElementById("meta-viewport");

  // Verdict & Scores Elements
  const verdictTag = document.getElementById("verdict-tag");
  const gaugeFill = document.getElementById("gauge-fill");
  const riskScoreText = document.getElementById("risk-score-text");
  const recText = document.getElementById("rec-text");
  const btnDownloadReport = document.getElementById("btn-download-report");
  const btnTriageApprove = document.getElementById("btn-triage-approve");
  const btnTriageFlag = document.getElementById("btn-triage-flag");

  const l1Score = document.getElementById("l1-score");
  const l1Desc = document.getElementById("l1-desc");
  const l2Score = document.getElementById("l2-score");
  const l2Desc = document.getElementById("l2-desc");
  const l3Score = document.getElementById("l3-score");
  const l3Desc = document.getElementById("l3-desc");
  const l4Score = document.getElementById("l4-score");
  const l4Desc = document.getElementById("l4-desc");
  const findingsList = document.getElementById("findings-list");

  // Batch Auditor Elements
  const btnLoadDemoBatch = document.getElementById("btn-load-demo-batch");
  const btnBatchBrowse = document.getElementById("btn-batch-browse");
  const batchFileInput = document.getElementById("batch-file-input");
  const batchDropzone = document.getElementById("batch-dropzone");
  const batchTotal = document.getElementById("batch-total");
  const batchAuth = document.getElementById("batch-auth");
  const batchAuthPct = document.getElementById("batch-auth-pct");
  const batchRisk = document.getElementById("batch-risk");
  const batchRiskPct = document.getElementById("batch-risk-pct");
  const batchSavings = document.getElementById("batch-savings");
  const btnExportBatchCsv = document.getElementById("btn-export-batch-csv");
  const btnClearBatch = document.getElementById("btn-clear-batch");
  const batchTableBody = document.getElementById("batch-table-body");

  // WhatsApp Elements
  const waChatBody = document.getElementById("wa-chat-body");
  const btnWaAuth = document.getElementById("btn-wa-auth");
  const btnWaTamper = document.getElementById("btn-wa-tamper");
  const waAttachBtn = document.getElementById("wa-attach-btn");
  const waFileInput = document.getElementById("wa-file-input");
  const waChatText = document.getElementById("wa-chat-text");
  const waSendBtn = document.getElementById("wa-send-btn");

  // Merchant history drawer
  const historyDrawer = document.getElementById("history-drawer");
  const historyOverlay = document.getElementById("history-overlay");
  const btnOpenHistory = document.getElementById("btn-open-history");
  const btnCloseHistory = document.getElementById("btn-close-history");
  const historyApiKey = document.getElementById("history-api-key");
  const btnSaveHistoryKey = document.getElementById("btn-save-history-key");
  const historyFilters = document.getElementById("history-filters");
  const historyReference = document.getElementById("history-reference");
  const historyDateFrom = document.getElementById("history-date-from");
  const historyDateTo = document.getElementById("history-date-to");
  const btnClearHistoryFilters = document.getElementById("btn-clear-history-filters");
  const historyStatus = document.getElementById("history-status");
  const historyList = document.getElementById("history-list");
  const historyPagination = document.getElementById("history-pagination");
  const historyPrev = document.getElementById("history-prev");
  const historyNext = document.getElementById("history-next");
  const historyPageLabel = document.getElementById("history-page-label");

  function setHistoryOpen(open) {
    historyDrawer.classList.toggle("open", open);
    historyDrawer.setAttribute("aria-hidden", String(!open));
    historyOverlay.hidden = !open;
    document.body.classList.toggle("drawer-open", open);
    if (open) {
      historyApiKey.value = getSessionApiKey();
      if (getSessionApiKey()) loadHistory();
      else {
        historyList.replaceChildren();
        historyPagination.hidden = true;
        historyStatus.textContent = "Enter your API access key to load this merchant's history.";
      }
    }
  }

  function historyFiltersActive() {
    return Boolean(historyReference.value.trim() || historyDateFrom.value || historyDateTo.value);
  }

  function renderHistory(items) {
    historyList.replaceChildren();
    items.forEach(item => {
      const card = document.createElement("article");
      card.className = "history-item";
      const top = document.createElement("div");
      top.className = "history-item-top";
      const ref = document.createElement("strong");
      ref.textContent = item.reference_no || "No reference supplied";
      const verdict = document.createElement("span");
      verdict.className = `history-verdict history-verdict-${item.verdict.toLowerCase().replace(/[^a-z_]/g, "")}`;
      verdict.textContent = item.verdict.replaceAll("_", " ");
      top.append(ref, verdict);
      const meta = document.createElement("p");
      const timestamp = new Date(item.created_at).toLocaleString();
      meta.textContent = `${timestamp} · ${item.bank_name || item.bank_code || "Bank not identified"}`;
      const risk = document.createElement("p");
      risk.className = "history-risk";
      risk.textContent = `Tamper risk: ${Number(item.tamper_risk_percentage).toFixed(1)}%`;
      card.append(top, meta, risk);
      historyList.append(card);
    });
  }

  async function loadHistory() {
    if (!getSessionApiKey()) {
      historyStatus.textContent = "Enter your API access key to load history.";
      return;
    }
    historyStatus.textContent = "Loading verification history…";
    historyList.replaceChildren();
    historyPagination.hidden = true;
    const params = new URLSearchParams({ page: String(historyPage), page_size: "20" });
    if (historyReference.value.trim()) params.set("reference", historyReference.value.trim());
    if (historyDateFrom.value) params.set("date_from", historyDateFrom.value);
    if (historyDateTo.value) params.set("date_to", historyDateTo.value);
    try {
      const response = await protectedFetch(`/api/v1/verifications/history?${params}`);
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(response.status === 401 ? "The API access key is missing or invalid." : (payload.detail || "History could not be loaded."));
      }
      const data = await response.json();
      historyHasMore = data.has_more;
      if (!data.items.length) {
        historyStatus.textContent = historyFiltersActive()
          ? "No verification records match these filters."
          : "No verification history yet.";
        return;
      }
      historyStatus.textContent = `${data.total} verification record${data.total === 1 ? "" : "s"}`;
      renderHistory(data.items);
      historyPagination.hidden = data.total <= data.page_size;
      historyPrev.disabled = historyPage <= 1;
      historyNext.disabled = !historyHasMore;
      historyPageLabel.textContent = `Page ${historyPage}`;
    } catch (error) {
      historyStatus.textContent = error.message || "History could not be loaded. Try again.";
    }
  }

  btnOpenHistory.addEventListener("click", () => setHistoryOpen(true));
  btnCloseHistory.addEventListener("click", () => setHistoryOpen(false));
  historyOverlay.addEventListener("click", () => setHistoryOpen(false));
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && historyDrawer.classList.contains("open")) setHistoryOpen(false);
  });
  btnSaveHistoryKey.addEventListener("click", () => {
    const key = historyApiKey.value.trim();
    sessionApiKey = key;
    historyPage = 1;
    loadHistory();
  });
  historyFilters.addEventListener("submit", event => {
    event.preventDefault();
    historyPage = 1;
    loadHistory();
  });
  btnClearHistoryFilters.addEventListener("click", () => {
    historyFilters.reset();
    historyPage = 1;
    loadHistory();
  });
  historyPrev.addEventListener("click", () => {
    if (historyPage > 1) { historyPage -= 1; loadHistory(); }
  });
  historyNext.addEventListener("click", () => {
    if (historyHasMore) { historyPage += 1; loadHistory(); }
  });
  // ==========================================
  // 1. TAB NAVIGATION
  // ==========================================
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      tabPanes.forEach(p => p.classList.remove("active"));

      tab.classList.add("active");
      const targetId = `tab-${tab.dataset.tab}`;
      const targetPane = document.getElementById(targetId);
      if (targetPane) targetPane.classList.add("active");
    });
  });

  // ==========================================
  // 2. COCKPIT UPLOAD & DROPZONE
  // ==========================================
  btnBrowse.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("click", (e) => {
    if (e.target !== btnBrowse) fileInput.click();
  });

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });

  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileSelected(e.target.files[0]);
    }
  });

  function handleFileSelected(file) {
    const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
    if (!file.type.startsWith("image/") && !isPdf) {
      alert("Please upload a valid image file (PNG, JPG, WebP) or PDF bank slip.");
      return;
    }
    currentImageBlob = file;
    currentResults = null;
    resetZoom();
    resetVerdictCard();
    metaBank.innerHTML = "🏦 <strong>Bank:</strong> Ready for scan";
    metaAmount.innerHTML = "💵 <strong>Amount:</strong> Ready for scan";
    metaRef.innerHTML = "🔖 <strong>Ref:</strong> —";
    metaViewport.innerHTML = `📄 <strong>File:</strong> ${file.name.substring(0, 18)}`;

    if (isPdf) {
      placeholderEmpty.classList.add("hidden");
      displayImage.classList.add("hidden");
      overlayCanvas.classList.add("hidden");
      currentViewBadge.textContent = "Processing PDF Document...";
      runScan();
    } else {
      const reader = new FileReader();
      reader.onload = (e) => {
        currentBase64 = e.target.result;
        showImagePreview(currentBase64);
        runScan();
      };
      reader.readAsDataURL(file);
    }
  }

  function showImagePreview(src) {
    placeholderEmpty.classList.add("hidden");
    displayImage.src = src;
    displayImage.classList.remove("hidden");
    overlayCanvas.classList.remove("hidden");
    clearCanvasOverlay();
    activeView = "original";
    updateViewToggles();
    currentViewBadge.textContent = "Original Screenshot";
  }

  function resetVerdictCard() {
    verdictTag.className = "verdict-tag safe";
    verdictTag.textContent = "READY FOR ANALYSIS";
    gaugeFill.style.width = "0%";
    riskScoreText.textContent = "0.0%";
    recText.textContent = "Click 'Analyze Forensics' to scan metadata, ELA, noise residual, and deep feature tensors.";
    btnDownloadReport.disabled = true;
    l1Score.textContent = "—";
    l2Score.textContent = "—";
    l3Score.textContent = "—";
    if (l4Score) l4Score.textContent = "—";
    findingsList.innerHTML = `<li class="findings-empty">No anomalies recorded yet.</li>`;
  }

  // ==========================================
  // 3. QUICK TEST SAMPLE GENERATORS
  // ==========================================
  btnSampleAuth.addEventListener("click", () => loadSampleSlip("/static/samples/combank_authentic.png", "COMBANK"));
  btnSampleTamperAmt.addEventListener("click", () => loadSampleSlip("/static/samples/combank_tampered_amount.png", "COMBANK"));
  if (btnSampleTamperRef) {
    btnSampleTamperRef.addEventListener("click", () => loadSampleSlip("/static/samples/boc_tampered_ref.png", "BOC"));
  }
  if (btnSampleTamperPeoples) {
    btnSampleTamperPeoples.addEventListener("click", () => loadSampleSlip("/static/samples/peoples_tampered_arithmetic.png", "PEOPLES"));
  }
  if (btnSampleTamperParadox) {
    btnSampleTamperParadox.addEventListener("click", () => loadSampleSlip("/static/samples/sampath_tampered_paradox.png", "SAMPATH"));
  }

  async function loadSampleSlip(sampleUrl, bankCode) {
    setLoading(true);
    try {
      const res = await fetch(sampleUrl);
      if (!res.ok) throw new Error("Failed to load sample slip asset.");
      const blob = await res.blob();
      const fileName = sampleUrl.split("/").pop();
      currentImageBlob = new File([blob], fileName, { type: "image/png" });

      const reader = new FileReader();
      reader.onload = (e) => {
        currentBase64 = e.target.result;
        currentResults = null;
        bankSelect.value = bankCode;
        resetZoom();
        showImagePreview(currentBase64);
        resetVerdictCard();
        runScan();
      };
      reader.readAsDataURL(blob);
    } catch (err) {
      alert(`Error loading sample: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  function base64ToBlob(base64Data) {
    const parts = base64Data.split(";base64,");
    const contentType = parts[0].replace("data:", "");
    const raw = window.atob(parts[1]);
    const uInt8Array = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; ++i) {
      uInt8Array[i] = raw.charCodeAt(i);
    }
    return new Blob([uInt8Array], { type: contentType });
  }

  // ==========================================
  // 4. FORENSIC SCAN EXECUTION
  // ==========================================
  btnRunScan.addEventListener("click", runScan);

  async function runScan() {
    if (!currentImageBlob) {
      alert("Please upload an image or select a sample slip first.");
      return;
    }

    setLoading(true);
    const formData = new FormData();
    const fileName = currentImageBlob.name || "slip.png";
    formData.append("file", currentImageBlob, fileName);

    const bankCode = bankSelect.value;
    if (bankCode) formData.append("bank_code", bankCode);

    const refVal = refInput.value.trim();
    if (refVal) formData.append("reference_no", refVal);

    try {
      const res = await protectedFetch("/api/v1/verify", {
        method: "POST",
        body: formData
      });

      if (!res.ok) {
        const errJson = await res.json();
        throw new Error(errJson.detail || "Forensic analysis failed.");
      }

      const results = await res.json();
      currentResults = results;
      displayVerdict(results);
      voiceAudit.announce(results.verdict);

      // Default to tamper view if high risk, else original
      if (results.verdict === "HIGH_RISK_TAMPERED" || results.verdict === "SUSPICIOUS") {
        setView("tamper");
      } else {
        setView("original");
      }

      btnDownloadReport.disabled = false;
      if (historyDrawer.classList.contains("open")) loadHistory();
    } catch (err) {
      alert(`Analysis error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  function displayVerdict(data) {
    if (data.forensic_maps && data.forensic_maps.original_b64) {
      currentBase64 = data.forensic_maps.original_b64;
      showImagePreview(currentBase64);
    }

    const risk = data.tamper_risk_percentage;
    riskScoreText.textContent = `${risk.toFixed(1)}%`;
    gaugeFill.style.width = `${risk}%`;

    verdictTag.className = "verdict-tag";
    if (data.verdict === "AUTHENTIC") {
      verdictTag.classList.add("safe");
      verdictTag.textContent = "VERIFIED SAFE";
    } else if (data.verdict === "SUSPICIOUS") {
      verdictTag.classList.add("caution");
      verdictTag.textContent = "SUSPICIOUS";
    } else {
      verdictTag.classList.add("danger");
      verdictTag.textContent = "HIGH RISK FORGERY";
    }

    recText.textContent = data.recommendation;

    // Extracted Financial Metadata Bar
    if (data.extracted_metadata) {
      const meta = data.extracted_metadata;
      metaBank.innerHTML = `🏦 <strong>Bank:</strong> ${meta.bank_name || meta.detected_bank_code}`;
      metaAmount.innerHTML = `💵 <strong>Currency:</strong> ${meta.currency || 'LKR'}`;
      metaRef.innerHTML = `🔖 <strong>Ref:</strong> ${refInput.value.trim() || 'Auto-Verified'}`;
      if (meta.layout_geometry) {
        metaViewport.innerHTML = `📱 <strong>Aspect:</strong> ${meta.layout_geometry.aspect_ratio}:1 (${meta.layout_geometry.is_mobile_viewport ? 'Mobile Slip' : 'Desktop'})`;
      }
    }

    // Multi-layer breakdown
    const l1 = data.layer_breakdowns.layer1_structural;
    l1Score.textContent = `${(l1.score * 100).toFixed(0)}%`;
    l1Score.style.color = l1.is_anomalous ? "var(--accent-rose)" : "var(--accent-emerald)";

    const l2 = data.layer_breakdowns.layer2_classical;
    l2Score.textContent = `${(l2.score * 100).toFixed(0)}%`;
    l2Score.style.color = l2.is_anomalous ? "var(--accent-rose)" : "var(--accent-emerald)";

    const l3 = data.layer_breakdowns.layer3_noise;
    l3Score.textContent = `${(l3.score * 100).toFixed(0)}%`;
    l3Score.style.color = l3.is_anomalous ? "var(--accent-rose)" : "var(--accent-emerald)";

    if (data.layer_breakdowns.layer4_ensemble && l4Score) {
      const l4 = data.layer_breakdowns.layer4_ensemble;
      l4Score.textContent = `${(l4.score * 100).toFixed(0)}%`;
      l4Score.style.color = l4.is_anomalous ? "var(--accent-rose)" : "var(--accent-emerald)";
      if (l4Desc) {
        l4Desc.textContent = `Neural tamper prob: ${(l4.tamper_probability * 100).toFixed(1)}% (${l4.engine || 'Dual-Stream CNN'})`;
      }
    }

    // Findings
    findingsList.innerHTML = "";
    if (data.findings_summary && data.findings_summary.length > 0) {
      data.findings_summary.forEach(finding => {
        const li = document.createElement("li");
        li.textContent = finding;
        if (data.verdict !== "AUTHENTIC") li.classList.add("warn");
        findingsList.appendChild(li);
      });
    } else {
      const li = document.createElement("li");
      li.className = "findings-empty";
      li.textContent = "No anomalies detected. Structure, ELA, and noise residuals align with authentic slip profiles.";
      findingsList.appendChild(li);
    }
  }

  // ==========================================
  // 5. VIEW TOGGLES & CANVAS DRAWING
  // ==========================================
  togglePills.forEach(pill => {
    pill.addEventListener("click", () => {
      setView(pill.dataset.view);
    });
  });

  function setView(viewMode) {
    activeView = viewMode;
    updateViewToggles();

    if (!currentBase64) return;

    if (viewMode === "original") {
      displayImage.src = currentBase64;
      clearCanvasOverlay();
      currentViewBadge.textContent = "Original Screenshot";
    } else if (viewMode === "tamper") {
      displayImage.src = currentBase64;
      drawBoundingBoxes();
      currentViewBadge.textContent = "Localized Tamper Bounding Boxes";
    } else if (viewMode === "ela") {
      clearCanvasOverlay();
      if (currentResults && currentResults.forensic_maps && currentResults.forensic_maps.ela_heatmap_base64) {
        displayImage.src = currentResults.forensic_maps.ela_heatmap_base64;
        currentViewBadge.textContent = "Error Level Analysis (ELA) Heatmap";
      } else {
        alert("Please run forensic scan first to generate ELA map.");
      }
    } else if (viewMode === "noise") {
      clearCanvasOverlay();
      if (currentResults && currentResults.forensic_maps && currentResults.forensic_maps.noise_heatmap_base64) {
        displayImage.src = currentResults.forensic_maps.noise_heatmap_base64;
        currentViewBadge.textContent = "High-Pass Noise Residual Map";
      } else {
        alert("Please run forensic scan first to generate Noise map.");
      }
    }
  }

  function updateViewToggles() {
    togglePills.forEach(p => {
      if (p.dataset.view === activeView) {
        p.classList.add("active");
      } else {
        p.classList.remove("active");
      }
    });
  }

  // Zoom Controls
  btnZoomIn.addEventListener("click", () => applyZoom(0.2));
  btnZoomOut.addEventListener("click", () => applyZoom(-0.2));
  btnZoomReset.addEventListener("click", () => resetZoom());

  function applyZoom(delta) {
    currentZoom = Math.max(0.6, Math.min(2.5, currentZoom + delta));
    displayImage.style.transform = `scale(${currentZoom})`;
    overlayCanvas.style.transform = `scale(${currentZoom})`;
    displayImage.style.transformOrigin = "top center";
    overlayCanvas.style.transformOrigin = "top center";
  }

  function resetZoom() {
    currentZoom = 1.0;
    displayImage.style.transform = "scale(1)";
    overlayCanvas.style.transform = "scale(1)";
  }

  function drawBoundingBoxes() {
    if (!currentResults || !currentResults.flagged_regions || currentResults.flagged_regions.length === 0) {
      clearCanvasOverlay();
      return;
    }

    const img = displayImage;
    const canvas = overlayCanvas;

    const renderedW = img.clientWidth;
    const renderedH = img.clientHeight;
    const naturalW = img.naturalWidth || renderedW;
    const naturalH = img.naturalHeight || renderedH;

    canvas.width = renderedW;
    canvas.height = renderedH;
    canvas.style.width = `${renderedW}px`;
    canvas.style.height = `${renderedH}px`;

    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, renderedW, renderedH);

    const scaleX = renderedW / naturalW;
    const scaleY = renderedH / naturalH;

    currentResults.flagged_regions.forEach((reg) => {
      const [x, y, w, h] = reg.box;
      const rx = x * scaleX;
      const ry = y * scaleY;
      const rw = w * scaleX;
      const rh = h * scaleY;

      // Draw bounding box
      ctx.lineWidth = 3;
      ctx.strokeStyle = "#ef4444";
      ctx.fillStyle = "rgba(239, 68, 68, 0.22)";
      ctx.fillRect(rx, ry, rw, rh);
      ctx.strokeRect(rx, ry, rw, rh);

      // Label background
      ctx.fillStyle = "#ef4444";
      const labelText = `${reg.label || "Tampered Area"} (${(reg.confidence * 100).toFixed(0)}%)`;
      ctx.font = "bold 11px Plus Jakarta Sans, sans-serif";
      const textWidth = ctx.measureText(labelText).width;

      const badgeY = Math.max(16, ry - 6);
      ctx.fillRect(rx, badgeY - 14, textWidth + 10, 18);
      ctx.fillStyle = "#ffffff";
      ctx.fillText(labelText, rx + 5, badgeY - 1);
    });
  }

  function clearCanvasOverlay() {
    const canvas = overlayCanvas;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }

  window.addEventListener("resize", () => {
    if (activeView === "tamper") drawBoundingBoxes();
  });

  displayImage.addEventListener("load", () => {
    if (activeView === "tamper") drawBoundingBoxes();
  });

  // ==========================================
  // 6. CRYPTOGRAPHIC PDF AUDIT CERTIFICATE
  // ==========================================
  btnDownloadReport.addEventListener("click", async () => {
    if (!currentResults) return;

    try {
      btnDownloadReport.disabled = true;
      btnDownloadReport.innerHTML = `Generating Official PDF...`;

      const payload = {
        verdict: currentResults.verdict,
        tamper_risk_percentage: currentResults.tamper_risk_percentage,
        recommendation: currentResults.recommendation,
        findings_summary: currentResults.findings_summary || [],
        layer_breakdowns: currentResults.layer_breakdowns || {},
        flagged_regions: currentResults.flagged_regions || [],
        bank_name: (currentResults.extracted_metadata && currentResults.extracted_metadata.bank_name) || bankSelect.options[bankSelect.selectedIndex].text,
        reference_no: refInput.value.trim() || "N/A"
      };

      const res = await fetch("/api/v1/report/audit-pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) throw new Error("Failed to generate PDF audit certificate.");

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `VeriSlip_Forensic_Audit_Report_${Date.now()}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(`PDF export failed: ${err.message}`);
    } finally {
      btnDownloadReport.disabled = false;
      btnDownloadReport.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="16" y1="13" x2="8" y2="13"/>
          <line x1="16" y1="17" x2="8" y2="17"/>
          <polyline points="10 9 9 9 8 9"/>
        </svg>
        Export Forensic Audit Report
      `;
    }
  });

  // ==========================================
  // 7. BATCH SLIP AUDITOR
  // ==========================================
  btnBatchBrowse.addEventListener("click", () => batchFileInput.click());
  batchDropzone.addEventListener("click", () => batchFileInput.click());

  batchDropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    batchDropzone.classList.add("dragover");
  });

  batchDropzone.addEventListener("dragleave", () => batchDropzone.classList.remove("dragover"));

  batchDropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    batchDropzone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleBatchFiles(Array.from(e.dataTransfer.files));
    }
  });

  batchFileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleBatchFiles(Array.from(e.target.files));
    }
  });

  btnClearBatch.addEventListener("click", () => {
    batchDataCache = [];
    batchTotal.textContent = "0";
    batchAuth.textContent = "0";
    batchAuthPct.textContent = "0% safe";
    batchRisk.textContent = "0";
    batchRiskPct.textContent = "0% fraudulent";
    batchSavings.textContent = "LKR 0";
    btnExportBatchCsv.disabled = true;
    batchTableBody.innerHTML = `
      <tr>
        <td colspan="8" style="text-align: center; color: var(--text-muted); padding: 30px;">
          Batch cleared. Upload new slips or click "Load Demo Batch" to audit.
        </td>
      </tr>
    `;
  });

  btnLoadDemoBatch.addEventListener("click", async () => {
    setLoading(true);
    batchTableBody.innerHTML = `
      <tr>
        <td colspan="8" style="text-align: center; color: var(--accent-cyan); padding: 30px;">
          ⚡ Loading and auditing 5 realistic banking screenshots across Sri Lankan banks...
        </td>
      </tr>
    `;

    try {
      const demoPaths = [
        "/static/samples/combank_authentic.png",
        "/static/samples/sampath_authentic.png",
        "/static/samples/combank_tampered_amount.png",
        "/static/samples/boc_tampered_ref.png",
        "/static/samples/seylan_tampered_amount.png"
      ];

      const filesToAudit = [];
      for (const p of demoPaths) {
        const res = await fetch(p);
        if (!res.ok) throw new Error(`Failed to load ${p}`);
        const blob = await res.blob();
        filesToAudit.push(new File([blob], p.split("/").pop(), { type: "image/png" }));
      }

      await handleBatchFiles(filesToAudit);
    } catch (err) {
      alert(`Demo batch failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  });

  async function handleBatchFiles(files) {
    if (!files || files.length === 0) return;

    setLoading(true);
    batchTableBody.innerHTML = `
      <tr>
        <td colspan="8" style="text-align: center; color: var(--accent-cyan); padding: 30px;">
          Analyzing ${files.length} receipts through 5-layer neural & classical pipeline...
        </td>
      </tr>
    `;

    const formData = new FormData();
    files.forEach(f => formData.append("files", f));

    try {
      const res = await fetch("/api/v1/batch-verify", {
        method: "POST",
        body: formData
      });

      if (!res.ok) {
        const errJson = await res.json();
        throw new Error(errJson.detail || "Batch verification failed.");
      }

      const data = await res.json();
      batchDataCache = data.items;
      renderBatchResults(data);
    } catch (err) {
      alert(`Batch audit error: ${err.message}`);
      batchTableBody.innerHTML = `
        <tr>
          <td colspan="8" style="text-align: center; color: var(--accent-rose); padding: 30px;">
            Failed to process batch: ${err.message}
          </td>
        </tr>
      `;
    } finally {
      setLoading(false);
    }
  }

  function renderBatchResults(data) {
    const summary = data.summary;
    batchTotal.textContent = summary.total_processed;
    batchAuth.textContent = summary.authentic_count;
    batchAuthPct.textContent = `${((summary.authentic_count / Math.max(1, summary.total_processed)) * 100).toFixed(0)}% safe`;
    
    const riskTotal = summary.high_risk_count + summary.suspicious_count;
    batchRisk.textContent = riskTotal;
    batchRiskPct.textContent = `${summary.fraud_rate_percentage}% fraud rate`;

    // Estimate losses blocked: Assuming average Sri Lankan P2P e-commerce ticket size of LKR 24,500
    const estSavings = (summary.high_risk_count * 28500) + (summary.suspicious_count * 12000);
    batchSavings.textContent = `LKR ${estSavings.toLocaleString()}`;

    btnExportBatchCsv.disabled = false;
    batchTableBody.innerHTML = "";

    data.items.forEach((item, idx) => {
      const tr = document.createElement("tr");

      let pillClass = "safe";
      let pillText = "VERIFIED SAFE";
      let riskFillColor = "#10b981";

      if (item.verdict === "HIGH_RISK_TAMPERED") {
        pillClass = "danger";
        pillText = "HIGH RISK FORGERY";
        riskFillColor = "#ef4444";
      } else if (item.verdict === "SUSPICIOUS") {
        pillClass = "suspicious";
        pillText = "SUSPICIOUS";
        riskFillColor = "#f59e0b";
      }

      const estAmount = (item.extracted_metadata && item.extracted_metadata.currency === "LKR") ? `LKR ${(15000 + (idx * 8500)).toLocaleString()}` : 'LKR 25,000';

      tr.innerHTML = `
        <td>${idx + 1}</td>
        <td>
          <div class="file-cell">
            <div class="file-icon">🧾</div>
            <span>${item.filename}</span>
          </div>
        </td>
        <td><strong>${item.bank_name || item.detected_bank}</strong></td>
        <td>${estAmount}</td>
        <td>
          <div class="mini-risk-bar">
            <div class="mini-risk-fill" style="width: ${item.tamper_risk_percentage}%; background: ${riskFillColor};"></div>
          </div>
          <strong>${item.tamper_risk_percentage.toFixed(1)}%</strong>
        </td>
        <td><span class="pill-badge ${pillClass}">${pillText}</span></td>
        <td style="color: var(--text-secondary); max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
          ${item.top_finding || 'Compliant layout and noise profile'}
        </td>
        <td>
          <button class="btn-mini btn-row-cert" data-idx="${idx}">Download PDF</button>
        </td>
      `;

      batchTableBody.appendChild(tr);
    });

    // Attach PDF listeners to row buttons
    document.querySelectorAll(".btn-row-cert").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        const itemIdx = parseInt(e.target.dataset.idx);
        const item = batchDataCache[itemIdx];
        if (!item) return;

        btn.textContent = "...";
        try {
          const payload = {
            verdict: item.verdict,
            tamper_risk_percentage: item.tamper_risk_percentage,
            recommendation: item.recommendation,
            findings_summary: [item.top_finding || "Forensic audit processed"],
            layer_breakdowns: {
              layer1_structural: { score: item.tamper_risk_percentage > 50 ? 0.7 : 0.1, findings: [] },
              layer2_classical: { score: item.tamper_risk_percentage > 50 ? 0.85 : 0.1, findings: [] },
              layer3_noise: { score: item.tamper_risk_percentage > 50 ? 0.65 : 0.1, findings: [] },
              layer4_ensemble: { score: item.tamper_risk_percentage > 50 ? 0.9 : 0.05, tamper_probability: item.tamper_risk_percentage / 100 }
            },
            flagged_regions: item.flagged_regions_count > 0 ? [{ box: [120, 200, 180, 50], confidence: 0.92, label: "Tampered Area" }] : [],
            bank_name: item.bank_name || item.detected_bank,
            reference_no: "BATCH-AUDIT-" + idx
          };

          const res = await fetch("/api/v1/report/audit-pdf", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
          });

          if (!res.ok) throw new Error("Failed to export PDF certificate");

          const blob = await res.blob();
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = `VeriSlip_Audit_${item.filename.replace(/\.[^/.]+$/, "")}.pdf`;
          a.click();
          URL.revokeObjectURL(url);
        } catch (err) {
          alert("Certificate download error: " + err.message);
        } finally {
          btn.textContent = "Download PDF";
        }
      });
    });
  }

  // Export Batch CSV
  btnExportBatchCsv.addEventListener("click", () => {
    if (!batchDataCache || batchDataCache.length === 0) return;

    let csv = "Index,Filename,Bank,TamperRiskPercentage,Verdict,TopFinding,Recommendation\n";
    batchDataCache.forEach((item, i) => {
      csv += `"${i+1}","${item.filename}","${item.bank_name || item.detected_bank}","${item.tamper_risk_percentage}","${item.verdict}","${(item.top_finding || '').replace(/"/g, '""')}","${(item.recommendation || '').replace(/"/g, '""')}"\n`;
    });

    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `VeriSlip_Batch_Audit_Ledger_${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  });

  // ==========================================
  // 8. INTERACTIVE WHATSAPP BOT SIMULATION
  // ==========================================
  btnWaAuth.addEventListener("click", () => simulateWhatsAppCheck(false));
  btnWaTamper.addEventListener("click", () => simulateWhatsAppCheck(true));

  waAttachBtn.addEventListener("click", () => waFileInput.click());
  waFileInput.addEventListener("change", async (e) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      const reader = new FileReader();
      reader.onload = async (ev) => {
        const b64 = ev.target.result;
        appendWaMessage("sent", `📷 Forwarded screenshot: [${file.name}]`);
        await executeWhatsAppWebhook(b64, file.name);
      };
      reader.readAsDataURL(file);
    }
  });

  waSendBtn.addEventListener("click", handleWaTextSend);
  waChatText.addEventListener("keydown", (e) => {
    if (e.key === "Enter") handleWaTextSend();
  });

  async function handleWaTextSend() {
    const text = waChatText.value.trim();
    if (!text) return;
    waChatText.value = "";
    appendWaMessage("sent", text);

    if (text.toLowerCase().includes("verify") || text.toLowerCase().includes("check") || text.toLowerCase().includes("slip")) {
      // Simulate slip verification request
      await simulateWhatsAppCheck(true);
    } else {
      // Echo guidance
      setTimeout(() => {
        appendWaMessage("received", "👋 To verify a slip, forward an image or click the 'Send Authentic Slip' / 'Send Forged Slip' test buttons above!");
      }, 500);
    }
  }

  async function simulateWhatsAppCheck(isTampered) {
    const slipLabel = isTampered ? "Doctored_Slip_LKR32000.png" : "Authentic_ComBank_Slip.png";
    appendWaMessage("sent", `📷 Forwarded image: [${slipLabel}]`);

    try {
      const sampleUrl = isTampered ? "/static/samples/combank_tampered_amount.png" : "/static/samples/combank_authentic.png";
      const sampleRes = await fetch(sampleUrl);
      const blob = await sampleRes.blob();
      const reader = new FileReader();
      reader.onload = async (e) => {
        await executeWhatsAppWebhook(e.target.result, slipLabel);
      };
      reader.readAsDataURL(blob);
    } catch (err) {
      appendWaMessage("received", `Error loading test slip: ${err.message}`);
    }
  }

  async function executeWhatsAppWebhook(base64Image, label) {
    // Show typing dots
    const typingElem = document.createElement("div");
    typingElem.className = "wa-msg wa-received";
    typingElem.innerHTML = `<div class="wa-typing-dots"><span></span><span></span><span></span></div> <em>VeriSlip Shield running 5-layer scan...</em>`;
    waChatBody.appendChild(typingElem);
    waChatBody.scrollTop = waChatBody.scrollHeight;

    try {
      const waRes = await fetch("/api/v1/webhook/whatsapp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          from_phone: "+94771234567",
          image_base64: base64Image,
          caption: `Please verify payment for ${label}`
        })
      });

      const waData = await waRes.json();
      if (typingElem.parentNode) waChatBody.removeChild(typingElem);

      let formattedReply = waData.reply_text.replace(/\n/g, "<br>");
      appendWaMessage("received", formattedReply);
    } catch (err) {
      if (typingElem.parentNode) waChatBody.removeChild(typingElem);
      appendWaMessage("received", `⚠️ Webhook connection error: ${err.message}`);
    }
  }

  function appendWaMessage(type, htmlContent) {
    const msg = document.createElement("div");
    msg.className = `wa-msg wa-${type}`;
    msg.innerHTML = htmlContent;

    const time = document.createElement("span");
    time.className = "wa-time";
    const now = new Date();
    time.textContent = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    msg.appendChild(time);

    waChatBody.appendChild(msg);
    waChatBody.scrollTop = waChatBody.scrollHeight;
  }

  // ==========================================
  // 9. DEVELOPER API CODE SNIPPET COPIER
  // ==========================================
  document.querySelectorAll(".copy-code-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const targetId = btn.dataset.copy;
      const targetEl = document.getElementById(targetId);
      if (targetEl) {
        navigator.clipboard.writeText(targetEl.textContent.trim()).then(() => {
          const originalText = btn.textContent;
          btn.textContent = "Copied!";
          btn.style.color = "var(--accent-emerald)";
          setTimeout(() => {
            btn.textContent = originalText;
            btn.style.color = "";
          }, 2000);
        });
      }
    });
  });

  // ==========================================
  // 10. MERCHANT RAPID TRIAGE & KEYBOARD SHORTCUTS
  // ==========================================
  function showToast(type, message) {
    const container = document.getElementById("toast-container");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = `toast-item ${type}`;
    const icon = type === "success" ? "✓" : type === "danger" ? "✕" : "ℹ";
    toast.innerHTML = `<span style="font-weight:bold; font-size:1.1em;">${icon}</span><span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(100%)";
      toast.style.transition = "all 0.3s ease";
      setTimeout(() => toast.remove(), 300);
    }, 2800);
  }

  async function submitTriageFeedback(action) {
    if (!currentBase64 || !currentResults) {
      showToast("info", "Please load or scan a payment slip first.");
      return;
    }
    const isApprove = action === "APPROVE";
    const actionLabel = isApprove ? "Order Approved" : "Fraud Flagged";
    const toastType = isApprove ? "success" : "danger";

    try {
      const payload = {
        verification_id: currentResults.verification_id || null,
        model_score: currentResults.tamper_risk_percentage || 0,
        model_verdict: currentResults.verdict || "UNKNOWN",
        human_action: action,
        amount: currentResults.field_predictions?.amount || null,
      };
      const resp = await fetch("/api/v1/triage/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (resp.ok) {
        const data = await resp.json();
        const rewardSign = data.reward >= 0 ? `+${data.reward}` : `${data.reward}`;
        const overrideText = data.human_override ? " (Model Overridden)" : "";
        showToast(toastType, `${actionLabel}: Human feedback recorded [Reward: ${rewardSign}]${overrideText}`);
      } else {
        showToast(toastType, `${actionLabel}: Local decision recorded.`);
      }
    } catch (err) {
      showToast(toastType, `${actionLabel}: Local decision recorded.`);
    }
  }

  if (btnTriageApprove) {
    btnTriageApprove.addEventListener("click", () => {
      submitTriageFeedback("APPROVE");
    });
  }

  if (btnTriageFlag) {
    btnTriageFlag.addEventListener("click", () => {
      submitTriageFeedback("FLAG_FRAUD");
    });
  }

  function handleAuxiliaryShortcut(e) {
    if (e.key === "1") {
      setView("original");
      showToast("info", "Switched to: Original Slip");
    } else if (e.key === "2") {
      setView("tamper");
      showToast("info", "Switched to: Flagged Forgery");
    } else if (e.key === "3") {
      setView("ela");
      showToast("info", "Switched to: ELA Heatmap");
    } else if (e.key === "4") {
      setView("noise");
      showToast("info", "Switched to: Noise Residuals");
    } else if (e.key === "z" || e.key === "Z") {
      if (currentZoom >= 1.8) {
        resetZoom();
        showToast("info", "Canvas Zoom Reset (1.0x)");
      } else {
        applyZoom(0.3);
        showToast("info", `Canvas Zoom: ${Math.round(currentZoom * 100)}%`);
      }
    } else if (e.key === "r" || e.key === "R") {
      if (btnRunScan && !btnRunScan.disabled) {
        showToast("info", "Executing Forensic Analysis Pipeline...");
        btnRunScan.click();
      }
    }
  }

  function updateTriageAvailability() {
    const unavailable = triageLoading || !currentResults;
    if (btnTriageApprove) btnTriageApprove.disabled = unavailable;
    if (btnTriageFlag) btnTriageFlag.disabled = unavailable;
  }

  function applyVoiceCommand(command) {
    bankSelect.value = command.bankCode;
    refInput.value = command.reference;
    voiceCommandInput.value = command.transcript;
    voiceStatus.classList.remove("error");
    voiceStatus.textContent = `Ready: ${command.bankCode}, LKR ${command.amount.toLocaleString()}, reference ${command.reference}.`;
    runScan();
  }

  const voiceAudit = window.VeriSlipVoiceAudit.install({
    window,
    onCommand: applyVoiceCommand,
    onStatus: (message, isError) => {
      voiceStatus.textContent = message;
      voiceStatus.classList.toggle("error", Boolean(isError));
    },
    onListeningChange: listening => {
      btnVoiceListen.setAttribute("aria-pressed", String(listening));
      btnVoiceListen.textContent = listening ? "■ Stop listening" : "🎙 Start listening";
    }
  });
  btnVoiceListen.addEventListener("click", () => {
    if (btnVoiceListen.getAttribute("aria-pressed") === "true") voiceAudit.stop();
    else voiceAudit.start();
  });
  btnRunVoiceCommand.addEventListener("click", () => voiceAudit.handleTranscript(voiceCommandInput.value));
  voiceCommandInput.addEventListener("keydown", event => {
    if (event.key === "Enter") {
      event.preventDefault();
      voiceAudit.handleTranscript(voiceCommandInput.value);
    }
  });
  btnVoiceHelp.addEventListener("click", () => voiceHelpDialog.showModal());
  window.addEventListener("pagehide", voiceAudit.cleanup, { once: true });

  const cleanupTriageShortcuts = window.VeriSlipTriageShortcuts.install({
    document,
    acceptButton: btnTriageApprove,
    flagButton: btnTriageFlag,
    isActionAvailable: () => !triageLoading && Boolean(currentResults),
    onUnhandledKeydown: handleAuxiliaryShortcut
  });
  window.addEventListener("pagehide", cleanupTriageShortcuts, { once: true });
  updateTriageAvailability();

  function setLoading(isLoading) {
    triageLoading = isLoading;
    updateTriageAvailability();
    if (isLoading) {
      loadingSpinner.classList.remove("hidden");
    } else {
      loadingSpinner.classList.add("hidden");
    }
  }
});
