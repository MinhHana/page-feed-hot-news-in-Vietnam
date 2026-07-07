const API_URL = "/api/news";
const REFRESH_MS = 2 * 60 * 1000;
const STORAGE_KEY = "vnnews:lastFeed:v1";
const SKELETON_COUNT = 8;

const state = {
  articles: [],
  sources: [],
  activeSource: "all",
  query: "",
  hydratedFromCache: false,
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
  backToTop: document.getElementById("back-to-top"),
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
      const image = article.image ? escapeHtml(article.image) : "";
      const imageHtml = image
        ? `<a class="news-thumb-link" href="${url}" target="_blank" rel="noopener noreferrer">
            <img class="news-thumb" src="${image}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="this.parentElement.remove()">
          </a>`
        : "";

      return `
        <li class="news-item${image ? " has-image" : ""}">
          <div class="news-item-body">
            ${imageHtml}
            <div class="news-content">
              <div class="news-meta">
                <span class="news-time">[${time}]</span>
                <span class="news-source">[${source}]</span>
                <span class="news-category">#${category}</span>
              </div>
              <h2 class="news-title">
                <a href="${url}" target="_blank" rel="noopener noreferrer">${title}</a>
              </h2>
              ${summary ? `<p class="news-summary">${summary}</p>` : ""}
            </div>
          </div>
        </li>
      `;
    })
    .join("");
}

function renderSkeleton() {
  if (!elements.list) return;

  const item = `
    <li class="news-item news-skeleton" aria-hidden="true">
      <div class="news-item-body">
        <div class="news-content">
          <div class="skeleton-line skeleton-meta"></div>
          <div class="skeleton-line skeleton-title"></div>
          <div class="skeleton-line skeleton-title short"></div>
          <div class="skeleton-line skeleton-text"></div>
        </div>
      </div>
    </li>`;

  elements.list.innerHTML = item.repeat(SKELETON_COUNT);
  if (elements.empty) elements.empty.classList.add("hidden");
}

function saveToCache(payload) {
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ payload, savedAt: Date.now() })
    );
  } catch (error) {
    // localStorage đầy hoặc bị chặn — bỏ qua, không ảnh hưởng chức năng.
  }
}

function hydrateFromCache() {
  let cached;
  try {
    cached = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
  } catch (error) {
    cached = null;
  }

  const payload = cached && cached.payload;
  if (!payload || !Array.isArray(payload.articles) || !payload.articles.length) {
    return false;
  }

  state.articles = payload.articles;
  state.sources = buildSourceList(payload);
  state.hydratedFromCache = true;

  elements.updatedAt.textContent = formatUpdatedAt(payload.updatedAt);
  renderFilters();
  renderArticles();
  setStatus("Bản lưu · đang cập nhật...", false);
  return true;
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

async function fetchNewsPayload(forceRefresh = false) {
  const url = `${API_URL}?t=${Date.now()}${forceRefresh ? "&refresh=1" : ""}`;
  const response = await fetch(url, {
    cache: "no-store",
    headers: { "Cache-Control": "no-cache" },
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  return response.json();
}

async function loadNews(forceRefresh = false) {
  if (!state.articles.length) {
    renderSkeleton();
  }
  setStatus(state.hydratedFromCache ? "Đang cập nhật..." : "Đang tải dữ liệu...", false);
  elements.error.classList.add("hidden");

  if (elements.refreshBtn) {
    elements.refreshBtn.disabled = true;
  }

  try {
    const payload = await fetchNewsPayload(forceRefresh);
    state.articles = payload.articles || [];
    state.sources = buildSourceList(payload);
    state.hydratedFromCache = false;
    saveToCache(payload);

    elements.updatedAt.textContent = formatUpdatedAt(payload.updatedAt);
    renderFilters();
    renderArticles();
    setStatus(`LIVE · ${payload.total || state.articles.length} tin`, true);
  } catch (error) {
    console.error("Feed load failed:", error);
    if (state.articles.length) {
      // Đã có dữ liệu (bản lưu) hiển thị — không xoá, chỉ báo trạng thái.
      setStatus("Mất kết nối · đang hiển thị bản lưu", false);
    } else {
      if (elements.list) elements.list.innerHTML = "";
      setStatus("Không tải được dữ liệu", false);
      elements.error.textContent =
        "Không tải được dữ liệu tin. Nếu dùng GitHub Pages, hãy deploy lên Render (xem README).";
      elements.error.classList.remove("hidden");
    }
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
    loadNews(true);
  });
}

hydrateFromCache();
loadNews();
setInterval(() => loadNews(false), REFRESH_MS);

const BACK_TO_TOP_OFFSET = 320;

function updateBackToTopVisibility() {
  if (!elements.backToTop) return;

  const shouldShow = window.scrollY > BACK_TO_TOP_OFFSET;
  elements.backToTop.classList.toggle("is-visible", shouldShow);
  elements.backToTop.setAttribute("aria-hidden", shouldShow ? "false" : "true");
  elements.backToTop.tabIndex = shouldShow ? 0 : -1;
}

function scrollToTop() {
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  window.scrollTo({ top: 0, behavior: prefersReducedMotion ? "auto" : "smooth" });
}

if (elements.backToTop) {
  elements.backToTop.addEventListener("click", scrollToTop);
  window.addEventListener("scroll", updateBackToTopVisibility, { passive: true });
  updateBackToTopVisibility();
}
