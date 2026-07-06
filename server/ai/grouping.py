"""Group articles into fixed news domains for map-reduce digest."""

from __future__ import annotations

import unicodedata
from typing import Any

GROUP_ECONOMY = "Kinh tế - Tài chính - Chứng khoán"
GROUP_DOMESTIC = "Thời sự - Chính trị - Xã hội"
GROUP_WORLD = "Quốc tế"
GROUP_LIFE = "Đời sống - Sức khỏe - Khoa học"
GROUP_SPORT = "Thể thao - Giải trí"

GROUP_ORDER = [
    GROUP_ECONOMY,
    GROUP_DOMESTIC,
    GROUP_WORLD,
    GROUP_LIFE,
    GROUP_SPORT,
]

ECONOMY_SOURCE_KEYS = {"cafef", "vneconomy", "vietstock", "24hmoney"}

ECONOMY_KEYWORDS = (
    "vn-index", "vnindex", "co phieu", "chung khoan", "chứng khoán", "cổ phiếu",
    "gia vang", "giá vàng", "ty gia", "tỷ giá", "lai suat", "lãi suất",
    "ngan hang", "ngân hàng", "doanh nghiep", "doanh nghiệp", "kinh te", "kinh tế",
    "tai chinh", "tài chính", "xuat khau", "xuất khẩu", "nhap khau", "nhập khẩu",
    "gdp", "lam phat", "lạm phát", "bat dong san", "bất động sản", "trai phieu",
    "trái phiếu", "usd", "dau tu", "đầu tư", "thi truong", "thị trường",
)

WORLD_KEYWORDS = (
    "nga ", "ukraine", "my ", "mỹ ", "trung quoc", "trung quốc", "chau au",
    "châu âu", "chau a", "nhat ban", "nhật bản", "han quoc", "hàn quốc",
    "trieu tien", "triều tiên", "israel", "iran", "gaza", "nato", "quoc te",
    "quốc tế", "the gioi", "thế giới", "putin", "trump", "eu ", "asean",
    "philippines", "thai lan", "thái lan", "campuchia", "lao ",
)

LIFE_KEYWORDS = (
    "suc khoe", "sức khỏe", "dinh duong", "dinh dưỡng", "benh", "bệnh",
    "bac si", "bác sĩ", "an uong", "ăn uống", "cong nghe", "công nghệ",
    "khoa hoc", "khoa học", "ai ", "tri tue nhan tao", "trí tuệ nhân tạo",
    "giao duc", "giáo dục", "du lich", "du lịch", "thoi tiet", "thời tiết",
    "moi truong", "môi trường", "xe ", "o to", "ô tô", "dien thoai", "điện thoại",
)

SPORT_KEYWORDS = (
    "bong da", "bóng đá", "the thao", "thể thao", "world cup", "premier league",
    "ngoai hang", "ngoại hạng", "cau thu", "cầu thủ", "hlv", "doi tuyen",
    "đội tuyển", "sea games", "olympic", "phim", "ca si", "ca sĩ", "dien vien",
    "diễn viên", "hoa hau", "hoa hậu", "nghe si", "nghệ sĩ", "showbiz",
    "am nhac", "âm nhạc", "giai tri", "giải trí", "mv ", "hau truong",
    "tennis", "bong ro", "bóng rổ", "the hinh",
)

DOMESTIC_KEYWORDS = (
    "chinh phu", "chính phủ", "quoc hoi", "quốc hội", "thu tuong", "thủ tướng",
    "bo chinh tri", "bộ chính trị", "tong bi thu", "tổng bí thư", "chu tich",
    "chủ tịch", "tinh ", "tỉnh ", "thanh pho", "thành phố", "cong an", "công an",
    "toa an", "tòa án", "vu an", "vụ án", "tai nan", "tai nạn", "chay ", "cháy ",
    "bao ", "bão ", "lu ", "lũ ", "giao thong", "giao thông",
)


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFD", value or "")
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return text.replace("đ", "d").replace("Đ", "D").lower()


def _score(haystack: str, keywords: tuple[str, ...]) -> int:
    return sum(1 for keyword in keywords if _normalize(keyword) in haystack)


def classify_article(article: dict[str, Any]) -> str:
    source_key = str(article.get("sourceKey", "")).lower()
    if source_key in ECONOMY_SOURCE_KEYS:
        return GROUP_ECONOMY

    haystack = _normalize(
        f"{article.get('title', '')} {article.get('summary', '')} "
        f"{article.get('category', '')}"
    )

    scores = {
        GROUP_ECONOMY: _score(haystack, ECONOMY_KEYWORDS),
        GROUP_WORLD: _score(haystack, WORLD_KEYWORDS),
        GROUP_SPORT: _score(haystack, SPORT_KEYWORDS),
        GROUP_LIFE: _score(haystack, LIFE_KEYWORDS),
        GROUP_DOMESTIC: _score(haystack, DOMESTIC_KEYWORDS),
    }

    best_group = max(scores, key=lambda key: scores[key])
    if scores[best_group] == 0:
        return GROUP_DOMESTIC
    return best_group


def group_articles(articles: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {name: [] for name in GROUP_ORDER}
    for article in articles:
        groups[classify_article(article)].append(article)
    return {name: items for name, items in groups.items() if items}
