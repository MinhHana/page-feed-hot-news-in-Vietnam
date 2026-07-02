# Vietnam News Matrix Feed

Trang web demo tổng hợp tin tức mới nhất từ các báo Việt Nam và **24HMoney**, hiển thị theo thứ tự từ mới đến cũ với giao diện phong cách ma trận.

## Nguồn dữ liệu

- VnExpress
- Tuổi Trẻ
- Thanh Niên
- Dân Trí
- Kenh14
- 24HMoney

## Chạy local

```bash
pip install -r scripts/requirements.txt
python scripts/fetch_news.py
python -m http.server 8080
```

Mở `http://localhost:8080`.

## GitHub Pages

1. Vào **Settings → Pages**
2. Source: branch `main`, folder `/ (root)`
3. Trang sẽ có tại: `https://<username>.github.io/page-feed-hot-news-in-Vietnam/`

## Tự động cập nhật

Workflow `.github/workflows/fetch-news.yml` chạy mỗi 30 phút (hoặc thủ công), fetch tin mới và commit `data/news.json`.

## Cấu trúc

```
├── index.html
├── assets/
│   ├── css/matrix.css
│   └── js/
│       ├── app.js
│       └── matrix-rain.js
├── data/news.json
├── scripts/fetch_news.py
└── .github/workflows/fetch-news.yml
```
