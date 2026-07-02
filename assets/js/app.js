const REPO = "MinhHana/page-feed-hot-news-in-Vietnam";
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
  refreshBtn: document.getElementById("refresh-btn"),
  empty: document.getElementById("empty-state"),
  error: document.getElementById("error-state"),
};

function getFeedUrls() {
  const pageUrl = new URL(window.location.href);

  if (!pageUrl.pathname.endsWith("/")) {
    if (/\.[a-z0-9]+$/i.test(pageUrl.pathname)) {
      pageUrl.pathname = pageUrl.pathname.replace(/\/[^/]*$/, "/");
    } else {
      pageUrl.pathname = `${pageUrl.pathname}/`;
    }
  }

  const localUrl = new URL("feed/news.json", pageUrl).href;

  return [
    localUrl,
    `https://cdn.jsdelivr.net/gh/${REPO}@main/feed/news.json`,
    `https://raw.githubusercontent.com/${REPO}/main/feed/news.json`,
  ];
}

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
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function normalizeText(value) {
  return String(value)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLowerCase()
    .trim();
}

function getSearchTokens(query) {
  return normalizeText(query).split(/\s+/).filter(Boolean);
}

function matchesSearch(article, tokens) {
  if (!tokens.length) return true;

  const haystack = normalizeText(
    `${article.title} ${article.summary} ${article.source} ${article.category}`
  );

  return tokens.every((token) => haystack.includes(token));
}

function getFilteredArticles() {
  const tokens = getSearchTokens(state.query);

  return state.articles.filter((article) => {
    const matchesSource =
      state.activeSource === "all" || article.sourceKey === state.activeSource;

    return matchesSource && matchesSearch(article, tokens);
  });
}

function renderFilters() {
  if (!elements.filters) return;

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
  const tokens = getSearchTokens(state.query);

  elements.count.textContent = `${filtered.length} bài viết`;
  elements.empty.classList.toggle("hidden", filtered.length > 0);

  if (tokens.length && filtered.length === 0) {
    elements.empty.textContent = `Không tìm thấy tin cho "${state.query.trim()}".`;
  } else {
    elements.empty.textContent = "Không tìm thấy tin phù hợp.";
  }

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

async function fetchNewsPayload() {
  const urls = getFeedUrls();
  const errors = [];

  for (const url of urls) {
    try {
      const response = await fetch(`${url}?t=${Date.now()}`, {
        cache: "no-store",
        headers: { "Cache-Control": "no-cache" },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      return response.json();
    } catch (error) {
      errors.push(`${url}: ${error.message}`);
    }
  }

  throw new Error(errors.join(" | "));
}

async function loadNews() {
  setStatus("Đang tải dữ liệu...", false);
  elements.error.classList.add("hidden");

  if (elements.refreshBtn) {
    elements.refreshBtn.disabled = true;
  }

  try {
    const payload = await fetchNewsPayload();
    state.articles = payload.articles || [];
    state.sources = buildSourceList(payload);

    elements.updatedAt.textContent = formatUpdatedAt(payload.updatedAt);
    renderFilters();
    renderArticles();
    setStatus(`LIVE · ${payload.total || state.articles.length} tin`, true);
  } catch (error) {
    setStatus("Không tải được dữ liệu", false);
    elements.error.textContent =
      "Không tải được dữ liệu tin. Thử nhấn TẢI LẠI TIN hoặc kiểm tra kết nối mạng.";
    elements.error.classList.remove("hidden");
    console.error("Feed load failed:", error);
  } finally {
    if (elements.refreshBtn) {
      elements.refreshBtn.disabled = false;
    }
  }
}

if (elements.search) {
  elements.search.addEventListener("input", (event) => {
    state.query = event.target.value;
    renderArticles();
  });

  elements.search.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      renderArticles();
    }
  });
}

if (elements.refreshBtn) {
  elements.refreshBtn.addEventListener("click", () => {
    loadNews();
  });
}

loadNews();
setInterval(loadNews, REFRESH_MS);
