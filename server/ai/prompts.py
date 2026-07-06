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
