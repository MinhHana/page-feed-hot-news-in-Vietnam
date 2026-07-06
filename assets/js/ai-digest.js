const AI_DIGEST_URL = "/api/ai/digest";
const AI_DIGEST_HOURS = 48;

const digestElements = {
  btn: document.getElementById("ai-digest-btn"),
  panel: document.getElementById("ai-digest-panel"),
  meta: document.getElementById("ai-digest-meta"),
  headline: document.getElementById("ai-digest-headline"),
  notice: document.getElementById("ai-digest-notice"),
  body: document.getElementById("ai-digest-body"),
  close: document.getElementById("ai-digest-close"),
  search: document.getElementById("search-input"),
};

const digestState = {
  loading: false,
};

function digestEscape(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function digestActiveSource() {
  const active = document.querySelector(".filter-btn.active");
  return active?.dataset.source || "all";
}

function setDigestLoading(isLoading) {
  digestState.loading = isLoading;
  if (digestElements.btn) {
    digestElements.btn.disabled = isLoading;
    digestElements.btn.textContent = isLoading
      ? "◎ ĐANG TỔNG HỢP..."
      : "📰 BẢN TIN TỔNG HỢP";
  }
}

function showDigestPanel() {
  digestElements.panel?.classList.remove("hidden");
}

function hideDigestPanel() {
  digestElements.panel?.classList.add("hidden");
}

function renderCitations(citations) {
  if (!Array.isArray(citations) || !citations.length) return "";
  const links = citations
    .map(
      (item) =>
        `<a class="ai-digest-cite" href="${digestEscape(item.url)}" target="_blank" rel="noopener noreferrer">${digestEscape(item.source)}</a>`
    )
    .join(" ");
  return `<span class="ai-digest-cites">${links}</span>`;
}

function renderPoint(point) {
  const text = digestEscape(point.text || "");
  return `<li class="ai-digest-point">${text} ${renderCitations(point.citations)}</li>`;
}

function renderDigest(payload) {
  showDigestPanel();

  const source = payload.source && payload.source !== "all" ? ` · ${payload.source}` : "";
  const provider = payload.provider ? ` · ${payload.provider}` : "";
  const cached = payload.cached ? " · cache" : "";
  digestElements.meta.textContent =
    `${payload.articleCount} bài · ${payload.hours}h${source}${provider}${cached}`;

  digestElements.headline.textContent = payload.headline || "";

  if (payload.message) {
    digestElements.notice.textContent = payload.message;
    digestElements.notice.classList.remove("hidden");
  } else {
    digestElements.notice.textContent = "";
    digestElements.notice.classList.add("hidden");
  }

  const blocks = [];

  const hotspots = Array.isArray(payload.hotspots) ? payload.hotspots : [];
  if (hotspots.length) {
    blocks.push(`
      <div class="ai-digest-section ai-digest-hotspots">
        <h3 class="ai-digest-section-title">🔥 ĐIỂM NÓNG</h3>
        <ul class="ai-digest-points">${hotspots.map(renderPoint).join("")}</ul>
      </div>
    `);
  }

  const sections = Array.isArray(payload.sections) ? payload.sections : [];
  for (const section of sections) {
    const points = Array.isArray(section.points) ? section.points : [];
    if (!points.length) continue;
    blocks.push(`
      <div class="ai-digest-section">
        <h3 class="ai-digest-section-title">${digestEscape(section.title)}</h3>
        <ul class="ai-digest-points">${points.map(renderPoint).join("")}</ul>
      </div>
    `);
  }

  digestElements.body.innerHTML =
    blocks.join("") || '<p class="ai-digest-empty">Không có nội dung tổng hợp.</p>';
}

async function requestDigest() {
  if (digestState.loading) return;

  const source = digestActiveSource();

  setDigestLoading(true);
  showDigestPanel();
  digestElements.meta.textContent = "Đang tổng hợp toàn bộ tin...";
  digestElements.headline.textContent = "";
  digestElements.body.innerHTML =
    '<p class="ai-digest-empty">&gt; Grok đang đọc và tổng hợp tất cả bài viết theo chuyên mục... (có thể mất 15-20 giây)</p>';
  digestElements.notice.classList.add("hidden");

  try {
    const response = await fetch(AI_DIGEST_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source, hours: AI_DIGEST_HOURS }),
    });

    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      const message =
        payload?.detail?.message ||
        payload?.message ||
        "Không tạo được bản tin tổng hợp. Vui lòng thử lại.";
      digestElements.body.innerHTML = `<p class="ai-digest-empty">${digestEscape(message)}</p>`;
      digestElements.meta.textContent = "Bản tin tổng hợp · lỗi";
      return;
    }

    renderDigest(payload);
  } catch (error) {
    digestElements.body.innerHTML =
      '<p class="ai-digest-empty">Không kết nối được máy chủ AI.</p>';
    digestElements.meta.textContent = "Bản tin tổng hợp · lỗi";
    console.error("AI digest failed:", error);
  } finally {
    setDigestLoading(false);
  }
}

if (digestElements.btn) {
  digestElements.btn.addEventListener("click", requestDigest);
}

if (digestElements.close) {
  digestElements.close.addEventListener("click", hideDigestPanel);
}
