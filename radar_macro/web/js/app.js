/**
 * Radar Makro - Türkiye Yatırım & Portföy İstihbarat Terminali Denetleyicisi
 */

import { MacroAPI } from "./api.js";
import { state, subscribe, updateFilters, notify } from "./state.js";

// ---------------------------------------------------------------------------
// Canlı Dünya Saatleri (İstanbul Ön Planda)
// ---------------------------------------------------------------------------
function initClocks() {
  function update() {
    const now = new Date();
    const formatTime = (tz) =>
      now.toLocaleTimeString("tr-TR", { timeZone: tz, hour: "2-digit", minute: "2-digit", second: "2-digit" });

    const ny = document.getElementById("clock-ny");
    const lon = document.getElementById("clock-lon");
    const fra = document.getElementById("clock-fra");
    const ist = document.getElementById("clock-ist");

    if (ist) ist.textContent = formatTime("Europe/Istanbul");
    if (ny) ny.textContent = formatTime("America/New_York");
    if (lon) lon.textContent = formatTime("Europe/London");
    if (fra) fra.textContent = formatTime("Europe/Berlin");
  }
  update();
  setInterval(update, 1000);
}

// ---------------------------------------------------------------------------
// Bildirim Mesajı (Toast)
// ---------------------------------------------------------------------------
function showToast(msg, isError = false) {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = "toast";
  if (isError) toast.style.borderColor = "#ef4444";
  toast.innerHTML = `<span>${isError ? "⚠️" : "🏛️"}</span> <span>${msg}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(100%)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// ---------------------------------------------------------------------------
// Arayüz Çiziciler (Renderers)
// ---------------------------------------------------------------------------
function renderMetrics(metrics) {
  const critEl = document.getElementById("metric-critical");
  const totEl = document.getElementById("metric-total");
  const warnEl = document.getElementById("metric-warning");
  const srcEl = document.getElementById("metric-sources");

  if (critEl) critEl.textContent = metrics.critical_count ?? 0;
  if (totEl) totEl.textContent = metrics.total_analyses ?? 0;
  if (warnEl) warnEl.textContent = metrics.warning_count ?? 0;
  if (srcEl) srcEl.textContent = metrics.active_sources_count ?? 14;
}

function getStanceClass(stance) {
  const s = String(stance || "NÖTR").toUpperCase();
  if (s.includes("ŞAHİN") || s.includes("HAWK")) return "stance-hawkish";
  if (s.includes("GÜVERCİN") || s.includes("DOV")) return "stance-dovish";
  if (s.includes("EKSEN") || s.includes("PIVOT")) return "stance-pivot";
  return "stance-neutral";
}

function renderBulletins(data) {
  const container = document.getElementById("bulletin-list");
  const countEl = document.getElementById("bulletin-count");
  if (!container) return;

  if (countEl) countEl.textContent = `${data.total} analiz bülteni`;

  if (!data.items || data.items.length === 0) {
    container.innerHTML = `
      <div style="background: rgba(15,23,42,0.6); border: 1px dashed rgba(148,163,184,0.2); border-radius: 8px; padding: 40px 20px; text-align: center; color: #94a3b8;">
        <div style="font-size: 2.2rem; margin-bottom: 8px;">🏛️</div>
        <div style="font-weight: 700; font-size: 1.05rem; color: #f1f5f9;">Mevcut filtrelere uygun makro bülten veya kararname bulunamadı</div>
        <div style="font-size: 0.85rem; margin-top: 6px;">Filtreleri esnetebilir veya "İstihbarat Döngüsünü Başlat" butonuna tıklayarak Resmî Gazete, TCMB ve BDDK akışını güncelleyebilirsiniz.</div>
      </div>
    `;
    return;
  }

  container.innerHTML = data.items
    .map((item) => {
      const stanceClass = getStanceClass(item.policy_stance);
      const isImmediate = String(item.regulatory_urgency).toUpperCase().includes("ACİL") || String(item.regulatory_urgency).toUpperCase().includes("IMMEDIATE");
      const urgencyClass = isImmediate ? "urgency-badge immediate" : "urgency-badge";
      const isTr = (item.jurisdiction && (item.jurisdiction.toLowerCase() === "turkey" || item.jurisdiction.toLowerCase() === "türkiye"));
      const flag = isTr ? "🇹🇷" : "🌐";

      // Varlık Etki Çipleri
      const assetChips = Object.entries(item.asset_impact || {})
        .map(([asset, dir]) => {
          const dirStr = String(dir);
          const dirLower = dirStr.toLowerCase();
          const chipClass = (dirLower.includes("pozitif") || dirLower.includes("lehine") || dirLower.includes("bull"))
            ? "asset-chip bullish"
            : (dirLower.includes("negatif") || dirLower.includes("aleyhine") || dirLower.includes("bear"))
            ? "asset-chip bearish"
            : "asset-chip neutral";
          return `<span class="${chipClass}"><b>${asset}:</b> ${dirStr}</span>`;
        })
        .join("");

      // BIST Şirket Duyarlılık Çipleri (Öne Çıkanlar & Baskılananlar)
      const bistTickers = item.bist_tickers || {};
      const favoredList = bistTickers.favored || [];
      const pressuredList = bistTickers.pressured || [];

      let bistChipsHtml = "";
      if (favoredList.length > 0 || pressuredList.length > 0) {
        const favChips = favoredList.slice(0, 3).map((f) => `<span class="ticker-chip favored">🟢 ${f.ticker}</span>`).join("");
        const presChips = pressuredList.slice(0, 2).map((p) => `<span class="ticker-chip pressured">🔴 ${p.ticker}</span>`).join("");
        bistChipsHtml = `
          <div class="bist-tickers-row">
            <span style="font-size: 0.72rem; color: #94a3b8; align-self: center; font-weight: 600; margin-right: 4px;">BIST Etkisi:</span>
            ${favChips}
            ${presChips}
          </div>
        `;
      }

      const dateStr = item.created_at
        ? new Date(item.created_at).toLocaleDateString("tr-TR", {
            day: "numeric",
            month: "short",
            hour: "2-digit",
            minute: "2-digit",
          })
        : "Yakın Zaman";

      return `
        <div class="bulletin-card" data-id="${item.id}">
          <div class="card-top">
            <div class="card-badges">
              <span class="stance-badge ${stanceClass}">${item.policy_stance}</span>
              <span class="${urgencyClass}">${String(item.regulatory_urgency || "İZLEME").replace(/_/g, " ")}</span>
              <span class="jurisdiction-tag">${flag} ${item.jurisdiction || "Türkiye"}</span>
              <span style="font-size: 0.76rem; color: #64748b; font-weight: 600; margin-left: 4px;">${item.source_name}</span>
            </div>
            <span style="font-size: 0.75rem; color: #64748b; font-family: var(--font-mono);">${dateStr}</span>
          </div>

          <div class="card-title">${item.title}</div>

          ${bistChipsHtml}

          ${item.simple_summary ? `<div class="card-simple-preview">💡 <b>Özet:</b> ${item.simple_summary}</div>` : ""}

          <div class="card-meta">
            <span>Önem Skoru: <b style="color: #60a5fa;">${item.relevance_score || 85}/100</b></span>
            <span>Kategori: ${item.category}</span>
            <a href="${item.url}" target="_blank" onclick="event.stopPropagation();" style="font-size: 0.78rem;">🔗 Resmî Kaynak</a>
          </div>

          ${assetChips ? `<div class="asset-impact-row">${assetChips}</div>` : ""}
        </div>
      `;
    })
    .join("");

  // Kart tıklama ile açılır detay penceresini açma
  container.querySelectorAll(".bulletin-card").forEach((card) => {
    card.addEventListener("click", () => {
      const id = parseInt(card.dataset.id, 10);
      const found = data.items.find((b) => b.id === id);
      if (found) openModal(found);
    });
  });
}

// ---------------------------------------------------------------------------
// Detay Açılır Penceresi (Modal / Slide-Over)
// ---------------------------------------------------------------------------
function openModal(item) {
  state.selectedBulletin = item;
  const overlay = document.getElementById("bulletin-modal");
  if (!overlay) return;

  const isTr = (item.jurisdiction && (item.jurisdiction.toLowerCase() === "turkey" || item.jurisdiction.toLowerCase() === "türkiye"));
  const flag = isTr ? "🇹🇷" : "🌐";
  const stanceClass = getStanceClass(item.policy_stance);

  document.getElementById("modal-badges").innerHTML = `
    <span class="stance-badge ${stanceClass}">${item.policy_stance}</span>
    <span class="urgency-badge">${String(item.regulatory_urgency || "İZLEME").replace(/_/g, " ")}</span>
    <span class="jurisdiction-tag">${flag} ${item.jurisdiction || "Türkiye"}</span>
    <span style="font-size: 0.8rem; color: #94a3b8; font-weight: 600;">${item.source_name}</span>
  `;

  document.getElementById("modal-title").textContent = item.title;

  // Çift Katmanlı Açıklamaların Doldurulması
  const simpleEl = document.getElementById("modal-simple");
  const techEl = document.getElementById("modal-technical");

  if (simpleEl) {
    simpleEl.textContent = item.simple_summary || (
      item.detailed_reasoning && item.detailed_reasoning.includes("💡 BASİTÇE NE DEMEK?")
        ? item.detailed_reasoning.split("🔬")[0].replace("💡 BASİTÇE NE DEMEK? (HERKES İÇİN):", "").trim()
        : "Bu karar, piyasalardaki likidite ve döviz dengesini etkileyebilecek bir makroekonomik veya yasal düzenlemedir."
    );
  }

  if (techEl) {
    techEl.textContent = item.technical_analysis || (
      item.detailed_reasoning && item.detailed_reasoning.includes("🔬")
        ? item.detailed_reasoning.split("🔬")[1].replace("TEKNİK ANALİZ & MAKRO YAYILIM MEKANİZMASI (PROFESYONELLER İÇİN):", "").trim()
        : item.detailed_reasoning || "Detaylı teknik analiz kaydı bulunamadı."
    );
  }

  // BIST 30/100 Şirket ve Sektör Duyarlılık Bölümü
  const bistContainer = document.getElementById("modal-bist-tickers");
  if (bistContainer) {
    const bist = item.bist_tickers || {};
    const favored = bist.favored || [];
    const pressured = bist.pressured || [];

    if (favored.length === 0 && pressured.length === 0) {
      bistContainer.innerHTML = `<div style="color: #64748b; font-size: 0.85rem;">Doğrudan tekil BIST hissesi üzerinde asimetrik bir ayrışma oluşturmamaktadır.</div>`;
    } else {
      let html = "";
      if (favored.length > 0) {
        html += `<div style="font-size: 0.82rem; font-weight: 700; color: #34d399; margin-bottom: 6px;">🟢 Olumlu Etkilenmesi Beklenen Şirketler:</div>`;
        favored.forEach((f) => {
          html += `
            <div class="bist-modal-card favored">
              <b>${f.ticker}:</b> ${f.reason}
            </div>
          `;
        });
      }
      if (pressured.length > 0) {
        html += `<div style="font-size: 0.82rem; font-weight: 700; color: #f87171; margin-top: 10px; margin-bottom: 6px;">🔴 Baskılanması / Temkinli Olunması Gerekenler:</div>`;
        pressured.forEach((p) => {
          html += `
            <div class="bist-modal-card pressured">
              <b>${p.ticker}:</b> ${p.reason}
            </div>
          `;
        });
      }
      bistContainer.innerHTML = html;
    }
  }

  const actionsContainer = document.getElementById("modal-actions");
  if (item.action_items && item.action_items.length > 0) {
    actionsContainer.innerHTML = item.action_items
      .map((act, i) => `<div class="action-box"><b>${i + 1}.</b> ${act}</div>`)
      .join("");
  } else {
    actionsContainer.innerHTML = `<div style="color: #64748b; font-size: 0.85rem;">Standart portföy takibi tavsiye edilmektedir.</div>`;
  }

  const assetContainer = document.getElementById("modal-assets");
  if (item.asset_impact && Object.keys(item.asset_impact).length > 0) {
    assetContainer.innerHTML = Object.entries(item.asset_impact)
      .map(([asset, dir]) => {
        const dirStr = String(dir);
        const dirLower = dirStr.toLowerCase();
        const color = (dirLower.includes("pozitif") || dirLower.includes("lehine") || dirLower.includes("bull"))
          ? "#34d399"
          : (dirLower.includes("negatif") || dirLower.includes("aleyhine") || dirLower.includes("bear"))
          ? "#f87171"
          : "#94a3b8";
        return `<div style="display: flex; justify-content: space-between; align-items: center; padding: 7px 0; border-bottom: 1px solid rgba(148,163,184,0.08); font-size: 0.86rem;">
          <span style="color: #cbd5e1; font-weight: 600;">${asset}</span>
          <span style="color: ${color}; font-weight: 700;">${dirStr}</span>
        </div>`;
      })
      .join("");
  } else {
    assetContainer.innerHTML = `<div style="color: #64748b; font-size: 0.85rem;">Doğrudan varlık yönü işlenmemiştir.</div>`;
  }

  document.getElementById("modal-raw-text").textContent = item.content_text || "";
  document.getElementById("modal-link").href = item.url || "#";
  document.getElementById("modal-hash").textContent = item.content_hash ? `SHA-256: ${item.content_hash}` : "";

  overlay.classList.add("active");
}

function closeModal() {
  const overlay = document.getElementById("bulletin-modal");
  if (overlay) overlay.classList.remove("active");
  state.selectedBulletin = null;
}

// ---------------------------------------------------------------------------
// SEKME 2: PORTFÖY & TAKTİKSEL DAĞILIM ÇİZİCİSİ ("Şundan Çık, Şuna Geç")
// ---------------------------------------------------------------------------
const ASSET_NAMES = {
  bist: "BIST Hisseleri",
  mevduat: "TL Mevduat & PPF",
  doviz: "Döviz Nakit (USD/EUR)",
  dibs: "DİBS & Eurobond",
  altin: "Gram Altın",
};

async function loadPortfolioData() {
  try {
    const copilot = await MacroAPI.getPortfolio();
    state.portfolio = copilot;
    renderPortfolio(copilot);
    await loadMemoryDigests();
    await loadAgentMemo();
  } catch (err) {
    console.error("Portföy verisi yüklenemedi:", err);
    showToast(`Portföy analizi yüklenemedi: ${err.message}`, true);
  }
}

async function loadAgentMemo() {
  const headlineEl = document.getElementById("agent-headline");
  if (!headlineEl) return;

  try {
    const res = await MacroAPI.getAgentMemo();
    const memo = res.memo;
    if (!memo) {
      headlineEl.textContent = "Henüz Stratejist Raporu Bulunmuyor";
      if (document.getElementById("agent-simple-guidance")) {
        document.getElementById("agent-simple-guidance").textContent = "Antigravity Ajanı henüz güncel bir baş stratejist notu kaydetmedi. Chat üzerinden 'Antigravity analizi güncelle' diyerek anında yeni bir analiz ürettirebilirsiniz.";
      }
      if (document.getElementById("agent-tech-analysis")) {
        document.getElementById("agent-tech-analysis").textContent = "Beklemede...";
      }
      return;
    }

    if (document.getElementById("agent-author-title")) {
      document.getElementById("agent-author-title").textContent = (memo.author || "ANTIGRAVITY BAŞ STRATEJİST MASASI").toUpperCase();
    }
    headlineEl.textContent = memo.headline || "Taktiksel Makro Değerlendirme";
    if (document.getElementById("agent-verdict")) {
      document.getElementById("agent-verdict").textContent = `📌 Makro Teşhis: ${memo.macro_verdict || "Dengeli"}`;
    }
    if (document.getElementById("agent-memo-date")) {
      const dt = memo.created_at ? new Date(memo.created_at).toLocaleString("tr-TR") : "Güncel";
      document.getElementById("agent-memo-date").textContent = `🕒 Rapor: ${dt}`;
    }
    if (document.getElementById("agent-simple-guidance")) {
      document.getElementById("agent-simple-guidance").textContent = memo.summary_guidance || "-";
    }
    if (document.getElementById("agent-tech-analysis")) {
      document.getElementById("agent-tech-analysis").textContent = memo.technical_analysis || "-";
    }

    const tickersContainer = document.getElementById("agent-tickers-container");
    if (tickersContainer) {
      const favs = memo.favored_tickers || [];
      const prss = memo.pressured_tickers || [];

      let html = "";
      favs.forEach((f) => {
        html += `
          <div class="agent-ticker-tag fav">
            <div class="agent-ticker-symbol">🟢 ${f.ticker || f} ${f.name ? `<span style="font-weight: normal; font-size: 0.8rem; color: #94a3b8;">(${f.name})</span>` : ""}</div>
            <div class="agent-ticker-reason">${f.reason || "Pozitif bilanço ve makro kalkan."}</div>
          </div>
        `;
      });
      prss.forEach((p) => {
        html += `
          <div class="agent-ticker-tag prs">
            <div class="agent-ticker-symbol">🔴 ${p.ticker || p} ${p.name ? `<span style="font-weight: normal; font-size: 0.8rem; color: #94a3b8;">(${p.name})</span>` : ""}</div>
            <div class="agent-ticker-reason">${p.reason || "Yüksek finansman maliyeti veya marj baskısı."}</div>
          </div>
        `;
      });
      tickersContainer.innerHTML = html || "<div style='color: #94a3b8; font-size: 0.85rem;'>Hisse yönlendirmesi mevcut değil.</div>";
    }
  } catch (err) {
    console.error("Ajan strateji raporu yüklenemedi:", err);
  }
}

async function loadMemoryDigests() {
  const container = document.getElementById("memory-digests-container");
  if (!container) return;

  try {
    const digests = await MacroAPI.getMemoryDigests();
    if (!digests || digests.length === 0) {
      container.innerHTML = `<div style="color: #94a3b8; font-size: 0.85rem; padding: 10px;">Henüz makro bellek kaydı bulunmamaktadır.</div>`;
      return;
    }

    const monthly = digests.filter((d) => d.period_type === "monthly").slice(0, 6);
    let itemsToShow = monthly.length > 0 ? monthly : digests.slice(0, 6);
    itemsToShow.sort((a, b) => (a.start_date || "").localeCompare(b.start_date || ""));

    container.innerHTML = itemsToShow
      .map((d) => {
        const stance = d.dominant_stance || "NÖTR";
        let badgeClass = "pivot";
        if (stance === "ŞAHİN") badgeClass = "hawkish";
        else if (stance === "GÜVERCİN") badgeClass = "dovish";

        const bist = d.bist_impact_summary || {};
        const favs = (bist.top_favored || []).slice(0, 3);
        const prss = (bist.top_pressured || []).slice(0, 3);

        const hwkPct = d.stance_distribution ? d.stance_distribution.hawkish_pct : 0;

        return `
          <div class="memory-card">
            <div class="memory-card-header">
              <span class="memory-card-label">📅 ${d.period_label || d.period_key}</span>
              <span class="memory-stance-badge ${badgeClass}">${stance} (%${hwkPct} Sıkılaşma)</span>
            </div>
            <div class="memory-narrative">${d.regime_narrative}</div>
            <div class="memory-bist-chips">
              ${favs.map((f) => `<span class="memory-chip-fav">🟢 ${f}</span>`).join("")}
              ${prss.map((p) => `<span class="memory-chip-prs">🔴 ${p}</span>`).join("")}
            </div>
          </div>
        `;
      })
      .join("");
  } catch (err) {
    console.error("Makro bellek yüklenemedi:", err);
  }
}

function renderPortfolio(copilot) {
  // 1. Rejim Başlığı ve Telemetri
  const titleEl = document.getElementById("portfolio-regime-title");
  const badgeEl = document.getElementById("regime-badge");
  const countEl = document.getElementById("stat-signal-count");
  const hawkEl = document.getElementById("stat-hawkish-pct");
  const dovEl = document.getElementById("stat-dovish-pct");
  const pivEl = document.getElementById("stat-pivot-pct");

  if (titleEl) titleEl.textContent = copilot.regime || "Dengeli Makro Rejim";
  if (badgeEl) {
    badgeEl.textContent = copilot.regime_code || "AKTİF";
    if (copilot.regime_code.includes("TIGHT")) {
      badgeEl.style.background = "rgba(239, 68, 68, 0.2)";
      badgeEl.style.color = "#f87171";
      badgeEl.style.borderColor = "rgba(239, 68, 68, 0.4)";
    } else if (copilot.regime_code.includes("EASING")) {
      badgeEl.style.background = "rgba(16, 185, 129, 0.2)";
      badgeEl.style.color = "#34d399";
      badgeEl.style.borderColor = "rgba(16, 185, 129, 0.4)";
    }
  }

  const stats = copilot.sentiment_stats || {};
  if (countEl) countEl.textContent = copilot.signals_analyzed_count ?? "-";
  if (hawkEl) hawkEl.textContent = `%${stats.hawkish_pct ?? 0}`;
  if (dovEl) dovEl.textContent = `%${stats.dovish_pct ?? 0}`;
  if (pivEl) pivEl.textContent = `%${stats.pivot_pct ?? 0}`;

  // 2. "Şundan Çık ➔ Şuna Geç" Direktif Kartları
  const actionsContainer = document.getElementById("tactical-actions-container");
  if (actionsContainer) {
    const actions = copilot.tactical_actions || [];
    if (actions.length === 0) {
      actionsContainer.innerHTML = `
        <div class="tactical-card" style="border-color: rgba(16, 185, 129, 0.4);">
          <div class="tactical-headline">✅ Portföyünüz Makro Rejimle Tam Uyumlu</div>
          <div class="tactical-instruction">Şu an için radikal bir varlık değişimi yapmanıza gerek yoktur.</div>
        </div>
      `;
    } else {
      actionsContainer.innerHTML = actions
        .map((act) => {
          const isRealloc = act.action_type === "REALLOCATE";
          const borderColor = isRealloc ? "rgba(245, 158, 11, 0.6)" : "rgba(16, 185, 129, 0.5)";
          return `
            <div class="tactical-card" style="border-color: ${borderColor};">
              <div class="tactical-headline">${act.headline}</div>
              <div class="tactical-instruction">${act.instruction}</div>
            </div>
          `;
        })
        .join("");
    }
  }

  // 3. Çift Katmanlı Gerekçelendirme Metinleri
  const simpleRatEl = document.getElementById("portfolio-simple-rationale");
  const techRatEl = document.getElementById("portfolio-tech-rationale");
  const rationale = copilot.rationale || {};

  if (simpleRatEl) simpleRatEl.textContent = rationale.simple || "Gerekçe hazırlanıyor...";
  if (techRatEl) techRatEl.textContent = rationale.technical || "Teknik gerekçe hazırlanıyor...";

  // 4. Form Değerlerinin Doldurulması (Mevcut Ağırlıklar)
  const curWeights = copilot.current_weights || {};
  for (const [key, val] of Object.entries(curWeights)) {
    const slider = document.getElementById(`slider-${key}`);
    const num = document.getElementById(`num-${key}`);
    if (slider) slider.value = val;
    if (num) num.value = val;
  }
  updateTotalWeightsLabel();

  // 5. Hedef ve Karşılaştırma Barlarının Çizilmesi
  const compContainer = document.getElementById("comparison-bars-container");
  if (compContainer) {
    const targetWeights = copilot.target_weights || {};
    const diffs = copilot.weight_diffs || {};

    compContainer.innerHTML = Object.keys(targetWeights)
      .map((key) => {
        const cur = curWeights[key] ?? 0;
        const tgt = targetWeights[key] ?? 0;
        const diff = diffs[key] ?? 0;
        const label = ASSET_NAMES[key] || key;

        let diffBadge = `<span class="comp-diff neutral">%0.0</span>`;
        if (diff > 0) {
          diffBadge = `<span class="comp-diff positive">+%${diff} (Artırın)</span>`;
        } else if (diff < 0) {
          diffBadge = `<span class="comp-diff negative">-%${Math.abs(diff)} (Azaltın)</span>`;
        }

        return `
          <div class="comparison-row">
            <div class="comp-header">
              <span class="comp-title">${label}</span>
              <div>
                <span style="font-size: 0.76rem; color: #94a3b8; margin-right: 8px;">Mevcut: <b style="color: #60a5fa;">%${cur}</b> | Hedef: <b style="color: #34d399;">%${tgt}</b></span>
                ${diffBadge}
              </div>
            </div>
            <div class="bar-dual">
              <div class="bar-track" title="Mevcut Ağırlığınız: %${cur}">
                <div class="bar-fill current" style="width: ${Math.min(cur, 100)}%;"></div>
              </div>
              <div class="bar-track" title="Makro Önerilen Hedef: %${tgt}">
                <div class="bar-fill target" style="width: ${Math.min(tgt, 100)}%;"></div>
              </div>
            </div>
          </div>
        `;
      })
      .join("") + `
        <div class="comp-legend">
          <span><span class="legend-dot" style="background: #60a5fa;"></span>Mevcut Portföyünüz</span>
          <span><span class="legend-dot" style="background: #34d399;"></span>Makro Hedef Önerisi</span>
        </div>
      `;
  }

  // 6. BIST Şirket Seçici Rehberlik Listeleri
  const bistFavList = document.getElementById("bist-favored-list");
  const bistAvdList = document.getElementById("bist-avoid-list");
  const guidance = copilot.bist_guidance || {};

  if (bistFavList) {
    const favs = guidance.top_favored || [];
    bistFavList.innerHTML = favs
      .map(
        (item) => `
        <div class="guidance-item" style="border-left: 3px solid #10b981;">
          <div class="guidance-ticker" style="color: #34d399;">🟢 ${item.ticker} <span style="font-size: 0.8rem; color: #94a3b8; font-weight: 500;">(${item.name})</span></div>
          <div style="color: #cbd5e1; line-height: 1.4;">${item.reason}</div>
        </div>
      `
      )
      .join("");
  }

  if (bistAvdList) {
    const avds = guidance.top_avoid || [];
    bistAvdList.innerHTML = avds
      .map(
        (item) => `
        <div class="guidance-item" style="border-left: 3px solid #ef4444;">
          <div class="guidance-ticker" style="color: #f87171;">🔴 ${item.ticker} <span style="font-size: 0.8rem; color: #94a3b8; font-weight: 500;">(${item.name})</span></div>
          <div style="color: #cbd5e1; line-height: 1.4;">${item.reason}</div>
        </div>
      `
      )
      .join("");
  }
}

function updateTotalWeightsLabel() {
  const keys = ["bist", "mevduat", "doviz", "dibs", "altin"];
  let total = 0;
  keys.forEach((k) => {
    const num = document.getElementById(`num-${k}`);
    if (num) total += parseFloat(num.value) || 0;
  });

  const tag = document.getElementById("weights-total-tag");
  if (tag) {
    tag.textContent = `Toplam: %${Math.round(total)}`;
    if (Math.round(total) === 100) {
      tag.style.color = "#34d399";
      tag.style.borderColor = "rgba(16, 185, 129, 0.4)";
      tag.style.background = "rgba(16, 185, 129, 0.15)";
    } else {
      tag.style.color = "#f87171";
      tag.style.borderColor = "rgba(239, 68, 68, 0.4)";
      tag.style.background = "rgba(239, 68, 68, 0.15)";
    }
  }
}

// ---------------------------------------------------------------------------
// Veri Yenileme ve Tarama Tetikleme
// ---------------------------------------------------------------------------
async function refreshData() {
  try {
    const [metrics, bulletinsData] = await Promise.all([
      MacroAPI.getMetrics(),
      MacroAPI.getBulletins(state.filters),
    ]);
    state.metrics = metrics;
    state.bulletins = bulletinsData.items || [];
    state.totalBulletins = bulletinsData.total || 0;

    renderMetrics(metrics);
    renderBulletins(bulletinsData);

    // Portföy sekmesi aktifse veya ilk açılışta portföy verisini de tazele
    if (state.activeTab === "portfolio") {
      await loadPortfolioData();
    }
  } catch (err) {
    console.error("Terminal verileri yüklenemedi:", err);
    showToast(`Veri yükleme hatası: ${err.message}`, true);
  }
}

async function triggerSurveillance() {
  if (state.isSyncing) return;
  const syncBtn = document.getElementById("btn-sync-trigger");
  state.isSyncing = true;
  if (syncBtn) {
    syncBtn.classList.add("spinning");
    syncBtn.disabled = true;
  }

  showToast("TCMB, Resmî Gazete, BDDK ve küresel piyasalar taranıyor...");

  try {
    await MacroAPI.triggerIngest({
      jurisdiction: state.filters.jurisdiction,
      batchSize: 8,
    });

    let attempts = 0;
    const interval = setInterval(async () => {
      attempts++;
      try {
        const metrics = await MacroAPI.getMetrics();
        const ingest = metrics.ingest_status || {};
        if (!ingest.is_running || attempts > 25) {
          clearInterval(interval);
          state.isSyncing = false;
          if (syncBtn) {
            syncBtn.classList.remove("spinning");
            syncBtn.disabled = false;
          }

          const stats = ingest.last_stats || {};
          const ing = stats.ingestion || {};
          const proc = stats.processing || {};
          showToast(`İstihbarat tarama döngüsü tamamlandı! Yeni: ${ing.new_saved || 0} | Analiz Edilen: ${proc.analyzed || 0}`);
          refreshData();
          loadPortfolioData();
        }
      } catch (e) {
        clearInterval(interval);
        state.isSyncing = false;
        if (syncBtn) {
          syncBtn.classList.remove("spinning");
          syncBtn.disabled = false;
        }
      }
    }, 1500);
  } catch (err) {
    state.isSyncing = false;
    if (syncBtn) {
      syncBtn.classList.remove("spinning");
      syncBtn.disabled = false;
    }
    showToast(`Tarama başlatılamadı: ${err.message}`, true);
  }
}

// ---------------------------------------------------------------------------
// Sekme Yönetimi (Tab Switching)
// ---------------------------------------------------------------------------
function initTabs() {
  const btnFeed = document.getElementById("tab-btn-feed");
  const btnPort = document.getElementById("tab-btn-portfolio");
  const viewFeed = document.getElementById("view-feed");
  const viewPort = document.getElementById("view-portfolio");

  if (btnFeed && btnPort && viewFeed && viewPort) {
    btnFeed.addEventListener("click", () => {
      state.activeTab = "feed";
      btnFeed.classList.add("active");
      btnPort.classList.remove("active");
      viewFeed.classList.add("active");
      viewPort.classList.remove("active");
    });

    btnPort.addEventListener("click", () => {
      state.activeTab = "portfolio";
      btnPort.classList.add("active");
      btnFeed.classList.remove("active");
      viewPort.classList.add("active");
      viewFeed.classList.remove("active");
      loadPortfolioData();
    });
  }
}

// ---------------------------------------------------------------------------
// Portföy Formu & Slider Senkronizasyonu
// ---------------------------------------------------------------------------
function initPortfolioSliders() {
  const keys = ["bist", "mevduat", "doviz", "dibs", "altin"];

  keys.forEach((k) => {
    const slider = document.getElementById(`slider-${k}`);
    const num = document.getElementById(`num-${k}`);

    if (slider && num) {
      slider.addEventListener("input", (e) => {
        num.value = e.target.value;
        updateTotalWeightsLabel();
      });

      num.addEventListener("input", (e) => {
        slider.value = e.target.value;
        updateTotalWeightsLabel();
      });
    }
  });

  const form = document.getElementById("portfolio-form");
  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const weights = {};
      keys.forEach((k) => {
        const num = document.getElementById(`num-${k}`);
        weights[k] = parseFloat(num ? num.value : 0) || 0;
      });

      showToast("Portföy ağırlıkları kaydediliyor ve yapay zeka analizi yenileniyor...");
      try {
        const updated = await MacroAPI.updatePortfolio(weights);
        state.portfolio = updated;
        renderPortfolio(updated);
        showToast("✅ Taktiksel portföy dağılımı ve hamle direktifleri güncellendi!");
      } catch (err) {
        showToast(`Portföy güncellenemedi: ${err.message}`, true);
      }
    });
  }
}

// ---------------------------------------------------------------------------
// Olay Dinleyicileri (Event Listeners)
// ---------------------------------------------------------------------------
function initEvents() {
  // Sekme Değiştiriciler
  initTabs();

  // Portföy Sliderları
  initPortfolioSliders();

  // Veri Yenileme Butonu
  const syncBtn = document.getElementById("btn-sync-trigger");
  if (syncBtn) syncBtn.addEventListener("click", triggerSurveillance);

  // Arama Kutusu (Debounce ile)
  const searchInput = document.getElementById("search-input");
  let searchTimeout = null;
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        updateFilters({ search: e.target.value.trim(), page: 1 });
        refreshData();
      }, 300);
    });
  }

  // Coğrafya / Kapsam Butonları
  document.querySelectorAll("[data-jurisdiction]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-jurisdiction]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const jur = btn.dataset.jurisdiction;
      updateFilters({ jurisdiction: jur, page: 1 });
      refreshData();
    });
  });

  // Politika Duruşu Çoklu Seçim Butonları
  document.querySelectorAll("[data-stance]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const stance = btn.dataset.stance;
      let cur = [...state.filters.stances];
      if (cur.includes(stance)) {
        cur = cur.filter((s) => s !== stance);
        btn.classList.remove("active");
      } else {
        cur.push(stance);
        btn.classList.add("active");
      }
      updateFilters({ stances: cur, page: 1 });
      refreshData();
    });
  });

  // Modal kapatma
  const modalClose = document.getElementById("modal-close");
  const modalOverlay = document.getElementById("bulletin-modal");
  if (modalClose) modalClose.addEventListener("click", closeModal);
  if (modalOverlay) {
    modalOverlay.addEventListener("click", (e) => {
      if (e.target === modalOverlay) closeModal();
    });
  }
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
  });

  // Dinamik Model & API Ayarları Modalı
  initSettingsModal();
}

// ---------------------------------------------------------------------------
// Dinamik Model & API Anahtarı Yapılandırma Modalı
// ---------------------------------------------------------------------------
function initSettingsModal() {
  const modal = document.getElementById("settings-modal");
  const openBtn = document.getElementById("btn-open-settings");
  const closeBtn = document.getElementById("settings-modal-close");
  const saveBtn = document.getElementById("btn-save-settings");
  const saveFeedback = document.getElementById("settings-save-feedback");

  const geminiKeyInput = document.getElementById("cfg-gemini-key");
  const toggleGeminiBtn = document.getElementById("btn-toggle-gemini-key");
  const testGeminiBtn = document.getElementById("btn-test-gemini");
  const geminiModelSelect = document.getElementById("cfg-gemini-model-select");
  const geminiCustomWrap = document.getElementById("gemini-custom-wrap");
  const geminiCustomInput = document.getElementById("cfg-gemini-model-custom");
  const geminiBadge = document.getElementById("gemini-status-badge");
  const geminiFeedback = document.getElementById("gemini-test-result");

  const openaiKeyInput = document.getElementById("cfg-openai-key");
  const toggleOpenaiBtn = document.getElementById("btn-toggle-openai-key");
  const testOpenaiBtn = document.getElementById("btn-test-openai");
  const openaiReasoningSelect = document.getElementById("cfg-openai-reasoning-select");
  const openaiCustomWrap = document.getElementById("openai-custom-wrap");
  const openaiCustomInput = document.getElementById("cfg-openai-reasoning-custom");
  const openaiBadge = document.getElementById("openai-status-badge");
  const openaiFeedback = document.getElementById("openai-test-result");

  if (!modal || !openBtn) return;

  function openSettings() {
    modal.classList.add("active");
    loadSettings();
  }

  function closeSettings() {
    modal.classList.remove("active");
    if (geminiFeedback) geminiFeedback.className = "test-feedback-box hidden";
    if (openaiFeedback) openaiFeedback.className = "test-feedback-box hidden";
    if (saveFeedback) saveFeedback.textContent = "";
  }

  openBtn.addEventListener("click", openSettings);
  if (closeBtn) closeBtn.addEventListener("click", closeSettings);
  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeSettings();
  });

  // Password Visibility Toggles
  if (toggleGeminiBtn && geminiKeyInput) {
    toggleGeminiBtn.addEventListener("click", () => {
      geminiKeyInput.type = geminiKeyInput.type === "password" ? "text" : "password";
    });
  }
  if (toggleOpenaiBtn && openaiKeyInput) {
    toggleOpenaiBtn.addEventListener("click", () => {
      openaiKeyInput.type = openaiKeyInput.type === "password" ? "text" : "password";
    });
  }

  // Model Select custom toggles
  if (geminiModelSelect && geminiCustomWrap) {
    geminiModelSelect.addEventListener("change", () => {
      if (geminiModelSelect.value === "custom") {
        geminiCustomWrap.classList.remove("hidden");
      } else {
        geminiCustomWrap.classList.add("hidden");
      }
    });
  }
  if (openaiReasoningSelect && openaiCustomWrap) {
    openaiReasoningSelect.addEventListener("change", () => {
      if (openaiReasoningSelect.value === "custom") {
        openaiCustomWrap.classList.remove("hidden");
      } else {
        openaiCustomWrap.classList.add("hidden");
      }
    });
  }

  async function loadSettings() {
    try {
      const data = await MacroAPI.getSettings();
      if (geminiKeyInput) {
        geminiKeyInput.value = data.gemini_api_key_masked || "";
        geminiKeyInput.placeholder = data.gemini_api_key_set ? "Mevcut anahtar kayıtlı" : "AIzaSy...";
      }
      if (geminiBadge) {
        if (data.gemini_api_key_set) {
          geminiBadge.className = "badge-status-pill badge-active";
          geminiBadge.textContent = "● Aktif & Bağlı";
        } else {
          geminiBadge.className = "badge-status-pill badge-missing";
          geminiBadge.textContent = "○ Anahtar Eksik";
        }
      }

      // Gemini Model
      if (geminiModelSelect) {
        const hasOpt = Array.from(geminiModelSelect.options).some((o) => o.value === data.gemini_model);
        if (hasOpt) {
          geminiModelSelect.value = data.gemini_model;
          geminiCustomWrap.classList.add("hidden");
        } else {
          geminiModelSelect.value = "custom";
          geminiCustomWrap.classList.remove("hidden");
          if (geminiCustomInput) geminiCustomInput.value = data.gemini_model || "";
        }
      }

      // OpenAI Key & Status
      if (openaiKeyInput) {
        openaiKeyInput.value = data.openai_api_key_masked || "";
        openaiKeyInput.placeholder = data.openai_api_key_set ? "Mevcut anahtar kayıtlı" : "sk-proj-...";
      }
      if (openaiBadge) {
        if (data.openai_api_key_set) {
          openaiBadge.className = "badge-status-pill badge-active";
          openaiBadge.textContent = "● Aktif & Bağlı";
        } else {
          openaiBadge.className = "badge-status-pill badge-missing";
          openaiBadge.textContent = "○ Anahtar Eksik";
        }
      }

      // OpenAI Reasoning Model
      if (openaiReasoningSelect) {
        const hasOpt = Array.from(openaiReasoningSelect.options).some((o) => o.value === data.openai_model_reasoning);
        if (hasOpt) {
          openaiReasoningSelect.value = data.openai_model_reasoning;
          openaiCustomWrap.classList.add("hidden");
        } else {
          openaiReasoningSelect.value = "custom";
          openaiCustomWrap.classList.remove("hidden");
          if (openaiCustomInput) openaiCustomInput.value = data.openai_model_reasoning || "";
        }
      }
    } catch (err) {
      showToast(`Ayarlar okunamadı: ${err.message}`, true);
    }
  }

  // Test Gemini
  if (testGeminiBtn) {
    testGeminiBtn.addEventListener("click", async () => {
      geminiFeedback.className = "test-feedback-box feedback-loading";
      geminiFeedback.textContent = "⚡ Gemini bağlantısı test ediliyor...";
      const model = geminiModelSelect.value === "custom" ? (geminiCustomInput.value.trim() || "gemini-flash-latest") : geminiModelSelect.value;
      const key = geminiKeyInput.value.trim();

      try {
        const res = await MacroAPI.testSettings({
          provider: "gemini",
          api_key: key,
          model_name: model,
        });
        if (res.success) {
          geminiFeedback.className = "test-feedback-box feedback-success";
          geminiFeedback.textContent = `✅ ${res.message} - Model: ${res.model}`;
        } else {
          geminiFeedback.className = "test-feedback-box feedback-error";
          geminiFeedback.textContent = `❌ Test Başarısız: ${res.error}`;
        }
      } catch (err) {
        geminiFeedback.className = "test-feedback-box feedback-error";
        geminiFeedback.textContent = `❌ Hata: ${err.message}`;
      }
    });
  }

  // Test OpenAI
  if (testOpenaiBtn) {
    testOpenaiBtn.addEventListener("click", async () => {
      const model = openaiReasoningSelect.value === "custom" ? (openaiCustomInput.value.trim() || "o1") : openaiReasoningSelect.value;
      openaiFeedback.className = "test-feedback-box feedback-loading";
      openaiFeedback.textContent = `⚡ OpenAI bağlantısı test ediliyor (model: ${model})...`;
      const key = openaiKeyInput.value.trim();

      try {
        const res = await MacroAPI.testSettings({
          provider: "openai",
          api_key: key,
          model_name: model,
        });
        if (res.success) {
          openaiFeedback.className = "test-feedback-box feedback-success";
          openaiFeedback.textContent = `✅ ${res.message} - Model: ${res.model}`;
        } else {
          openaiFeedback.className = "test-feedback-box feedback-error";
          openaiFeedback.textContent = `❌ Test Başarısız: ${res.error}`;
        }
      } catch (err) {
        openaiFeedback.className = "test-feedback-box feedback-error";
        openaiFeedback.textContent = `❌ Hata: ${err.message}`;
      }
    });
  }

  // Save Settings
  if (saveBtn) {
    saveBtn.addEventListener("click", async () => {
      saveBtn.disabled = true;
      saveFeedback.textContent = "Kaydediliyor...";
      saveFeedback.style.color = "#60a5fa";

      const geminiModel = geminiModelSelect.value === "custom" ? geminiCustomInput.value.trim() : geminiModelSelect.value;
      const openaiModel = openaiReasoningSelect.value === "custom" ? openaiCustomInput.value.trim() : openaiReasoningSelect.value;

      const payload = {
        gemini_model: geminiModel,
        openai_model_reasoning: openaiModel,
      };

      const gKey = geminiKeyInput.value.trim();
      if (gKey && !gKey.includes("...") && !gKey.includes("****")) {
        payload.gemini_api_key = gKey;
      }

      const oKey = openaiKeyInput.value.trim();
      if (oKey && !oKey.includes("...") && !oKey.includes("****")) {
        payload.openai_api_key = oKey;
      }

      try {
        const res = await MacroAPI.updateSettings(payload);
        saveFeedback.style.color = "#34d399";
        saveFeedback.textContent = "✅ " + res.message;
        showToast("✅ Model ve API ayarları çalışma zamanına uygulandı!");
        setTimeout(() => {
          closeSettings();
          loadPortfolioData();
        }, 1200);
      } catch (err) {
        saveFeedback.style.color = "#f87171";
        saveFeedback.textContent = "❌ Hata: " + err.message;
        showToast(`Kaydedilemedi: ${err.message}`, true);
      } finally {
        saveBtn.disabled = false;
      }
    });
  }
}


// ---------------------------------------------------------------------------
// Başlatma (Init)
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  initClocks();
  initEvents();
  refreshData();
  loadPortfolioData();

  // Her 30 saniyede bir otomatik telemetri yenileme
  setInterval(refreshData, 30000);
});
