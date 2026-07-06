# Vietnam News Matrix Feed

Trang web tổng hợp tin tức mới nhất từ các báo Việt Nam và **24HMoney**, hiển thị theo thứ tự từ mới đến cũ với giao diện phong cách ma trận.

## Nguồn dữ liệu

- VnExpress, Tuổi Trẻ, Thanh Niên, Dân Trí, Kenh14 (RSS)
- CafeF (RSS), VnEconomy, Vietstock (scrape trang chủ)
- 24HMoney (scrape trang live)

## Khuyến nghị: Deploy lên Render (miễn phí)

**GitHub Pages chỉ phục vụ file tĩnh** — không chạy server, dễ bị cache và lỗi trên Safari iPhone.  
**Render** chạy Python server thật, fetch tin trực tiếp khi bạn mở trang.

### Các bước deploy Render (5 phút)

1. Đăng ký tài khoản tại [render.com](https://render.com) (miễn phí)
2. Vào **Dashboard → New → Blueprint**
3. Kết nối repo GitHub `page-feed-hot-news-in-Vietnam`
4. Render đọc file `render.yaml` và tự deploy
5. Sau ~3 phút, truy cập URL dạng: `https://vietnam-news-matrix.onrender.com`

### Hoặc deploy thủ công

1. **New → Web Service** → chọn repo
2. Cấu hình:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn server.main:app --host 0.0.0.0 --port $PORT`
   - **Plan:** Free
3. Deploy

### Lưu ý gói Free Render

| Đặc điểm | Chi tiết |
|----------|----------|
| Chi phí | Miễn phí |
| Tin mới | Server fetch trực tiếp, cache 10 phút |
| Nút TẢI LẠI | Gọi `/api/news?refresh=1` — lấy tin mới ngay |
| Khởi động | Sau 15 phút không truy cập, server ngủ — lần mở đầu mất ~30–50 giây |

## Chạy local

```bash
pip install -r requirements.txt
uvicorn server.main:app --reload --port 8000
```

Mở `http://localhost:8000`

API:
- `GET /api/news` — danh sách tin (cache 10 phút)
- `GET /api/news?refresh=1` — fetch tin mới ngay
- `GET /api/health` — kiểm tra server
- `GET /api/ai/status` — trạng thái AI (OpenAI/Gemini)
- `POST /api/ai/brief` — tóm tắt diễn biến tin mới (Phase 1)

## Tóm tắt AI (Phase 1)

Nút **✦ TÓM TẮT AI** trên trang web gọi `POST /api/ai/brief` để tóm tắt các tin mới trong 24 giờ.

### Cấu hình Grok API key trên Render

1. Lấy key tại [console.x.ai](https://console.x.ai) → **API Keys** → **Create API Key** (dạng `xai-...`)
2. Vào **Render Dashboard → vietnam-news-matrix → Environment**
2. Thêm biến môi trường:

| Biến | Mô tả |
|------|--------|
| `XAI_API_KEY` | API key Grok từ [console.x.ai](https://console.x.ai) (dạng `xai-...`) |
| `AI_GROK_MODEL` | Model Grok (mặc định `grok-4.3`) |
| `AI_ENABLED` | `true` / `false` (mặc định `true`) |
| `AI_DAILY_REQUEST_LIMIT` | Giới hạn request/ngày/IP (mặc định `50`) |
| `AI_BRIEF_CACHE_TTL` | Cache tóm tắt (giây, mặc định `900`) |

3. **Save Changes** → Render tự deploy lại

### Khi chưa có API key

Nút vẫn hoạt động ở chế độ **fallback**: liệt kê nhanh các tiêu đề tin mới nhất thay vì tóm tắt AI.

### Ví dụ gọi API

```bash
curl -X POST http://localhost:8000/api/ai/brief \
  -H "Content-Type: application/json" \
  -d '{"query":"vnindex","source":"all","hours":24}'
```

## Các host miễn phí khác (tham khảo)

| Host | Web server | Ghi chú |
|------|------------|---------|
| **[Render](https://render.com)** | Có (Python) | Khuyến nghị, dùng `render.yaml` sẵn |
| **[Railway](https://railway.app)** | Có | $5 credit/tháng, dễ deploy |
| **[Fly.io](https://fly.io)** | Có | Free tier hạn chế |
| **[Vercel](https://vercel.com)** | Serverless | Cần chuyển API sang serverless function |
| **[Cloudflare Workers](https://workers.cloudflare.com)** | Edge JS | Cần viết lại logic fetch bằng JS |
| **GitHub Pages** | Không | Chỉ file tĩnh, không phù hợp cho tin realtime |

## Cấu trúc

```
├── server/
│   ├── main.py             # FastAPI: web + API
│   └── ai/                 # Tóm tắt AI (Phase 1)
├── scripts/fetch_news.py   # Logic thu thập tin
├── feed/news.json          # Dữ liệu mẫu (chạy local, không cập nhật tự động)
├── index.html              # Giao diện Matrix
├── assets/                 # CSS, JS
├── render.yaml             # Cấu hình Render
└── requirements.txt
```

Tạo `feed/news.json` thủ công khi cần test local:

```bash
pip install -r scripts/requirements.txt
python scripts/fetch_news.py
```

## GitHub Pages (không khuyến nghị)

Vẫn có thể dùng GitHub Pages cho giao diện tĩnh, nhưng dữ liệu tin sẽ không realtime và dễ lỗi trên mobile. Dùng Render để có trải nghiệm đầy đủ. Không còn workflow tự động commit tin — Render fetch tin trực tiếp qua server.
