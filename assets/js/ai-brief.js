const AI_BRIEF_URL = "/api/ai/brief";
const AI_STATUS_URL = "/api/ai/status";

const aiElements = {
  btn: document.getElementById("ai-brief-btn"),
  panel: document.getElementById("ai-brief-panel"),
  meta: document.getElementById("ai-brief-meta"),
  content: document.getElementById("ai-brief-content"),
  citations: document.getElementById("ai-brief-citations"),
  notice: document.getElementById("ai-brief-notice"),
  close: document.getElementById("ai-brief-close"),
  search: document.getElementById("search-input"),
};

const aiState = {
  status: null,
  loading: false,
};

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function getActiveSource() {
  const active = document.querySelector(".filter-btn.active");
  return active?.dataset.source || "all";
}

function formatBriefText(text) {
  return escapeHtml(text).replace(/\n/g, "<br>");
}

function setBriefLoading(isLoading) {
  aiState.loading = isLoading;
  if (aiElements.btn) {
    aiElements.btn.disabled = isLoading;
    aiElements.btn.textContent = isLoading ? "◎ ĐANG TÓM TẮT..." : "✦ TÓM TẮT AI";
  }
}

function showBriefPanel() {
  aiElements.panel?.classList.remove("hidden");
}

function hideBriefPanel() {
  aiElements.panel?.classList.add("hidden");
}

function renderBrief(payload) {
  if (!aiElements.panel) return;

  showBriefPanel();

  const topic = payload.query ? ` · "${payload.query}"` : "";
  const provider = payload.provider ? ` · ${payload.provider}` : "";
  const cached = payload.cached ? " · cache" : "";

  aiElements.meta.textContent =
    `${payload.articleCount} bài · ${payload.hours}h${topic}${provider}${cached}`;

  aiElements.content.innerHTML = formatBriefText(payload.brief || "");

  if (payload.message) {
    aiElements.notice.textContent = payload.message;
    aiElements.notice.classList.remove("hidden");
  } else {
    aiElements.notice.textContent = "";
    aiElements.notice.classList.add("hidden");
  }

  const citations = Array.isArray(payload.citations) ? payload.citations : [];
  if (!citations.length) {
    aiElements.citations.innerHTML = "";
    aiElements.citations.classList.add("hidden");
    return;
  }

  aiElements.citations.classList.remove("hidden");
  aiElements.citations.innerHTML = citations
    .map(
      (item) => `
        <a class="ai-brief-citation" href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">
          [${escapeHtml(item.source)}] ${escapeHtml(item.title)}
        </a>
      `
    )
    .join("");
}

async function loadAiStatus() {
  try {
    const response = await fetch(AI_STATUS_URL, { cache: "no-store" });
    if (!response.ok) return;
    aiState.status = await response.json();
    updateAiButtonHint();
  } catch (error) {
    console.warn("AI status unavailable:", error);
  }
}

function updateAiButtonHint() {
  if (!aiElements.btn || !aiState.status) return;

  if (aiState.status.configured) {
    aiElements.btn.title = "Tóm tắt diễn biến tin mới bằng AI (OpenAI/Gemini)";
    return;
  }

  aiElements.btn.title =
    "Tóm tắt nhanh danh sách tin (thêm API key trên Render để bật AI đầy đủ)";
}

async function requestBrief() {
  if (aiState.loading) return;

  const query = aiElements.search?.value.trim() || "";
  const source = getActiveSource();

  setBriefLoading(true);
  showBriefPanel();
  aiElements.meta.textContent = "Đang phân tích tin tức...";
  aiElements.content.textContent = "> AI đang đọc các bài mới nhất...";
  aiElements.citations.innerHTML = "";
  aiElements.citations.classList.add("hidden");
  aiElements.notice.classList.add("hidden");

  try {
    const response = await fetch(AI_BRIEF_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, source, hours: 24 }),
    });

    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      const message =
        payload?.detail?.message ||
        payload?.message ||
        "Không tạo được tóm tắt AI. Vui lòng thử lại.";
      aiElements.content.textContent = message;
      aiElements.meta.textContent = "AI Brief · lỗi";
      aiElements.notice.textContent = response.status === 429 ? "Đã vượt giới hạn trong ngày." : "";
      aiElements.notice.classList.toggle("hidden", response.status !== 429);
      return;
    }

    renderBrief(payload);
  } catch (error) {
    aiElements.content.textContent = "Không kết nối được máy chủ AI.";
    aiElements.meta.textContent = "AI Brief · lỗi";
    console.error("AI brief failed:", error);
  } finally {
    setBriefLoading(false);
  }
}

if (aiElements.btn) {
  aiElements.btn.addEventListener("click", requestBrief);
}

if (aiElements.close) {
  aiElements.close.addEventListener("click", hideBriefPanel);
}

loadAiStatus();
