const DATA_URL = "feed/news.json";
const REFRESH_MS = 2 * 60 * 1000;

const state = {
  articles: [],
  sources: [],
  activeSource: "all",
  query: "",
};

const elements = {
  list: document.getElementById("news-list"),
  count: document.getElementById("article-count"),
  updatedAt: document.getElementById("updated-at"),
  statusDot: document.getElementById("status-dot"),
  statusText: document.getElementById("status-text"),
  filters: document.getElementById("source-filters"),
  search: document.getElementById("search-input"),
  empty: document.getElementById("empty-state"),
  error: document.getElementById("error-state"),
};

function formatTime(isoString) {
  if (!isoString) return "--:--";
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return "--:--";

  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Ho_Chi_Minh",
  }).format(date);
}

function formatUpdatedAt(isoString) {
  if (!isoString) return "Cập nhật: --";
  return `Cập nhật: ${formatTime(isoString)}`;
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function getFilteredArticles() {
  const query = state.query.trim().toLowerCase();

  return state.articles.filter((article) => {
    const matchesSource =
      state.activeSource === "all" || article.sourceKey === state.activeSource;

    if (!matchesSource) return false;
    if (!query) return true;

    const haystack = `${article.title} ${article.summary} ${article.source} ${article.category}`.toLowerCase();
    return haystack.includes(query);
  });
}

function renderFilters() {
  const buttons = [
    `<button class="filter-btn active" data-source="all" type="button">TẤT CẢ</button>`,
    ...state.sources.map(
      (source) =>
        `<button class="filter-btn" data-source="${escapeHtml(source.key)}" type="button">${escapeHtml(source.name)}</button>`
    ),
  ];

  elements.filters.innerHTML = buttons.join("");

  elements.filters.querySelectorAll(".filter-btn").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeSource = button.dataset.source;
      elements.filters.querySelectorAll(".filter-btn").forEach((item) => {
        item.classList.toggle("active", item === button);
      });
      renderArticles();
    });
  });
}

function renderArticles() {
  const filtered = getFilteredArticles();
  elements.count.textContent = `${filtered.length} bài viết`;
  elements.empty.classList.toggle("hidden", filtered.length > 0);

  elements.list.innerHTML = filtered
    .map((article) => {
      const time = formatTime(article.publishedAt);
      const title = escapeHtml(article.title);
      const summary = escapeHtml(article.summary || "");
      const source = escapeHtml(article.source);
      const category = escapeHtml(article.category || "Tin tức");
      const url = escapeHtml(article.url);

      return `
        <li class="news-item">
          <div class="news-meta">
            <span class="news-time">[${time}]</span>
            <span class="news-source">[${source}]</span>
            <span class="news-category">#${category}</span>
          </div>
          <h2 class="news-title">
            <a href="${url}" target="_blank" rel="noopener noreferrer">${title}</a>
          </h2>
          ${summary ? `<p class="news-summary">${summary}</p>` : ""}
        </li>
      `;
    })
    .join("");
}

function setStatus(message, isLive = true) {
  elements.statusText.textContent = message;
  elements.statusDot.classList.toggle("live", isLive);
}

function buildSourceList(payload) {
  const map = new Map();
  for (const article of payload.articles || []) {
    if (!map.has(article.sourceKey)) {
      map.set(article.sourceKey, article.source);
    }
  }

  return Array.from(map, ([key, name]) => ({ key, name }));
}

async function loadNews() {
  setStatus("Đang tải dữ liệu...", false);
  elements.error.classList.add("hidden");

  try {
    const response = await fetch(`${DATA_URL}?t=${Date.now()}`, {
      cache: "no-store",
      headers: { "Cache-Control": "no-cache" },
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    state.articles = payload.articles || [];
    state.sources = buildSourceList(payload);

    elements.updatedAt.textContent = formatUpdatedAt(payload.updatedAt);
    renderFilters();
    renderArticles();
    setStatus(`LIVE · ${payload.total || state.articles.length} tin`, true);
  } catch (error) {
    setStatus("Không tải được dữ liệu", false);
    elements.error.textContent = `Lỗi: ${error.message}. Hãy chạy scripts/fetch_news.py để tạo feed/news.json.`;
    elements.error.classList.remove("hidden");
  }
}

elements.search.addEventListener("input", (event) => {
  state.query = event.target.value;
  renderArticles();
});

loadNews();
setInterval(loadNews, REFRESH_MS);
