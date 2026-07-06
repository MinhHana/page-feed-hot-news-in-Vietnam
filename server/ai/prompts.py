"""Prompt templates for AI brief generation."""

from __future__ import annotations

import json
from typing import Any


def build_brief_prompt(
    *,
    query: str,
    hours: int,
    articles: list[dict[str, Any]],
) -> str:
    topic_line = (
        f'Chủ đề người dùng quan tâm: "{query.strip()}".'
        if query.strip()
        else "Tổng hợp các diễn biến tin tức nổi bật nhất."
    )

    compact_articles = [
        {
            "id": article.get("id"),
            "title": article.get("title"),
            "summary": article.get("summary", ""),
            "source": article.get("source"),
            "category": article.get("category"),
            "publishedAt": article.get("publishedAt"),
            "url": article.get("url"),
        }
        for article in articles
    ]

    return f"""Bạn là biên tập viên tổng hợp tin tức Việt Nam.
{topic_line}
Chỉ được dùng thông tin trong danh sách bài viết dưới đây (trong {hours} giờ gần nhất).

Yêu cầu:
1. Viết tóm tắt tiếng Việt, 3-5 bullet ngắn gọn, mỗi bullet một diễn biến quan trọng.
2. Mỗi bullet phải dựa trên ít nhất một bài trong danh sách.
3. Không bịa số liệu, tên riêng, hay sự kiện không có trong danh sách.
4. Nếu thiếu tin, nói rõ "chưa đủ dữ liệu" thay vì suy đoán.
5. Trả về JSON hợp lệ theo schema:
{{
  "brief": "• bullet 1\\n• bullet 2\\n...",
  "citations": [
    {{"title": "...", "url": "...", "source": "..."}}
  ]
}}
6. citations chỉ chứa các bài đã dùng trong brief (tối đa 8 mục).

DANH SÁCH BÀI:
{json.dumps(compact_articles, ensure_ascii=False, indent=2)}"""


def _compact_articles(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": article.get("id"),
            "title": article.get("title"),
            "summary": article.get("summary", ""),
            "source": article.get("source"),
            "category": article.get("category"),
            "publishedAt": article.get("publishedAt"),
        }
        for article in articles
    ]


def build_map_prompt(
    *,
    group_name: str,
    hours: int,
    articles: list[dict[str, Any]],
) -> str:
    return f"""Bạn là biên tập viên tin tức Việt Nam, phụ trách chuyên mục "{group_name}".
Dưới đây là {len(articles)} bài trong {hours} giờ qua thuộc chuyên mục này.

Nhiệm vụ: rút ra TẤT CẢ diễn biến chính yếu, không bỏ sót sự kiện quan trọng.

Yêu cầu:
1. Gộp các bài viết về cùng một sự kiện thành một mục duy nhất.
2. Mỗi mục: 1-2 câu, GIỮ NGUYÊN số liệu, tên riêng, mốc thời gian quan trọng.
3. Sắp xếp theo mức độ quan trọng giảm dần.
4. TUYỆT ĐỐI không bịa thông tin ngoài danh sách.
5. Gắn id các bài nguồn cho mỗi mục (trường articleIds).
6. Trả về JSON hợp lệ:
{{
  "group": "{group_name}",
  "points": [
    {{"text": "...", "importance": 5, "articleIds": ["id1", "id2"]}}
  ]
}}
importance là số nguyên 1-5 (5 = quan trọng nhất).

DANH SÁCH BÀI (JSON):
{json.dumps(_compact_articles(articles), ensure_ascii=False, indent=2)}"""


def build_reduce_prompt(
    *,
    hours: int,
    map_results: list[dict[str, Any]],
) -> str:
    return f"""Bạn là tổng biên tập, tạo BẢN TIN TỔNG HỢP trong {hours} giờ qua cho độc giả bận rộn.
Dưới đây là các điểm tin đã được biên tập theo từng chuyên mục.

Nhiệm vụ: tạo bản digest giúp người đọc nắm TOÀN BỘ thông tin chính yếu.

Yêu cầu:
1. "headline": 1 câu mô tả bức tranh chung nổi bật nhất.
2. "hotspots": 5-7 diễn biến quan trọng nhất toàn bộ (chọn theo importance cao và tính thời sự).
3. "sections": giữ theo chuyên mục, mỗi chuyên mục liệt kê các diễn biến chính, gộp trùng lặp, bỏ mục trùng với hotspots nếu quá lặp.
4. Giữ số liệu, tên riêng, mốc thời gian. Ngắn gọn, không lặp, không bình luận cá nhân.
5. Chỉ dùng thông tin đã cung cấp. Giữ nguyên articleIds tương ứng cho mỗi mục.
6. Trả về JSON hợp lệ:
{{
  "headline": "...",
  "hotspots": [
    {{"text": "...", "articleIds": ["..."]}}
  ],
  "sections": [
    {{
      "title": "Tên chuyên mục",
      "points": [{{"text": "...", "articleIds": ["..."]}}]
    }}
  ]
}}

CÁC ĐIỂM TIN THEO CHUYÊN MỤC (JSON):
{json.dumps(map_results, ensure_ascii=False, indent=2)}"""
