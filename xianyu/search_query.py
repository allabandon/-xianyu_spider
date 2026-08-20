"""闲鱼 PC 搜索请求体。价格 / 地区编码对齐官网 mtop 筛选面板。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

SORT_OPTIONS = {
    "newest": ("create", "desc"),
    "price_asc": ("price", "asc"),
    "price_desc": ("price", "desc"),
    "default": ("", ""),
}


@dataclass(frozen=True)
class SearchFilters:
    sort: str = "newest"
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    province: Optional[str] = None
    city: Optional[str] = None
    publish_days: Optional[int] = None

    def normalized(self) -> "SearchFilters":
        sort = (self.sort or "newest").strip().lower()
        if sort not in SORT_OPTIONS:
            raise ValueError(f"不支持的排序: {self.sort}，可选 {', '.join(SORT_OPTIONS)}")
        min_price = self.min_price
        max_price = self.max_price
        if min_price is not None and min_price < 0:
            raise ValueError("min_price 不能小于 0")
        if max_price is not None and max_price < 0:
            raise ValueError("max_price 不能小于 0")
        if min_price is not None and max_price is not None and min_price > max_price:
            raise ValueError("min_price 不能大于 max_price")
        days = self.publish_days
        if days is not None and days < 1:
            raise ValueError("publish_days 必须大于 0")
        return SearchFilters(
            sort=sort,
            min_price=min_price,
            max_price=max_price,
            province=(self.province or "").strip() or None,
            city=(self.city or "").strip() or None,
            publish_days=days,
        )

    def public_dict(self) -> dict:
        data = self.normalized()
        payload: dict = {"sort": data.sort}
        if data.min_price is not None:
            payload["min_price"] = data.min_price
        if data.max_price is not None:
            payload["max_price"] = data.max_price
        if data.province:
            payload["province"] = data.province
        if data.city:
            payload["city"] = data.city
        if data.publish_days is not None:
            payload["publish_days"] = data.publish_days
        return payload


def _search_filter(filters: SearchFilters) -> str:
    parts: list[str] = []
    if filters.min_price is not None or filters.max_price is not None:
        low = 0 if filters.min_price is None else filters.min_price
        high = 99999999 if filters.max_price is None else filters.max_price
        parts.append(f"priceRange:{low},{high}")
    if filters.publish_days is not None:
        parts.append(f"publishDays:{filters.publish_days}")
    if not parts:
        return ""
    return ";".join(parts) + ";"


def _extra_filter_value(filters: SearchFilters) -> str:
    if not filters.province and not filters.city:
        return "{}"
    return json.dumps(
        {
            "divisionList": [
                {
                    "province": filters.province or "",
                    "city": filters.city or "",
                }
            ],
            "excludeMultiPlacesSellers": "0",
            "extraDivision": "",
        },
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _build_search_payload(keyword: str, page: int = 1, filters: SearchFilters | None = None) -> dict:
    data = (filters or SearchFilters()).normalized()
    sort_field, sort_value = SORT_OPTIONS[data.sort]
    has_extra = bool(
        data.min_price is not None
        or data.max_price is not None
        or data.province
        or data.city
        or data.publish_days is not None
    )
    from_filter = data.sort != "default" or has_extra
    return {
        "pageNumber": page,
        "keyword": keyword,
        "fromFilter": from_filter,
        "rowsPerPage": 30,
        "sortValue": sort_value,
        "sortField": sort_field,
        "customDistance": "",
        "gps": "",
        "propValueStr": {"searchFilter": _search_filter(data)},
        "customGps": "",
        "searchReqFromPage": "pcSearch",
        "extraFilterValue": _extra_filter_value(data),
        "userPositionJson": "{}",
    }


def build_search_payload(keyword: str, page: int = 1, filters: SearchFilters | None = None) -> dict:
    return _build_search_payload(keyword, page, filters)


build_search_payload = _build_search_payload
