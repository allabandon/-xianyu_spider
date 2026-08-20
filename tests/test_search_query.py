from xianyu.search_query import SearchFilters, build_search_payload


def test_default_payload_matches_newest_sort():
    payload = build_search_payload("手机", 1)
    assert payload["keyword"] == "手机"
    assert payload["pageNumber"] == 1
    assert payload["fromFilter"] is True
    assert payload["sortField"] == "create"
    assert payload["sortValue"] == "desc"
    assert payload["propValueStr"] == {"searchFilter": ""}
    assert payload["extraFilterValue"] == "{}"


def test_price_and_days_go_into_search_filter():
    payload = build_search_payload(
        "相机",
        2,
        SearchFilters(min_price=100, max_price=500, publish_days=7),
    )
    assert payload["pageNumber"] == 2
    assert payload["propValueStr"]["searchFilter"] == "priceRange:100,500;publishDays:7;"


def test_city_goes_into_extra_filter_value():
    payload = build_search_payload("自行车", 1, SearchFilters(city="深圳", province="广东"))
    assert "广东" in payload["extraFilterValue"]
    assert "深圳" in payload["extraFilterValue"]
    assert "divisionList" in payload["extraFilterValue"]


def test_price_asc_sort():
    payload = build_search_payload("电脑", 1, SearchFilters(sort="price_asc"))
    assert payload["sortField"] == "price"
    assert payload["sortValue"] == "asc"
    assert payload["fromFilter"] is True


def test_default_sort_without_filters_disables_from_filter():
    payload = build_search_payload("电脑", 1, SearchFilters(sort="default"))
    assert payload["fromFilter"] is False
    assert payload["sortField"] == ""


def test_invalid_sort_raises():
    try:
        SearchFilters(sort="hot").normalized()
    except ValueError as exc:
        assert "hot" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_min_price_greater_than_max_price_raises():
    try:
        SearchFilters(min_price=200, max_price=100).normalized()
    except ValueError as exc:
        assert "min_price" in str(exc)
    else:
        raise AssertionError("expected ValueError")
