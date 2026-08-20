import traceback

from fastapi import APIRouter, HTTPException

from xianyu.mtop import login_snapshot
from xianyu.schemas import SearchBody
from xianyu.search import save_to_db, scrape_xianyu_http

router = APIRouter()


@router.post(
    "/search/",
    summary="商品搜索接口",
    description="按关键词抓取商品。可指定排序、价格区间、地区；返回是否登录态。",
)
async def search_items(body: SearchBody):
    try:
        filters = body.filters()
        data_list = await scrape_xianyu_http(body.keyword, body.max_pages, filters=filters)
        new_count, new_ids = (0, [])
        if data_list:
            new_count, new_ids = await save_to_db(data_list)
        snapshot = login_snapshot()
        return {
            "status": "success",
            "keyword": body.keyword,
            "logged_in": bool(snapshot.get("logged_in")),
            "user_id": snapshot.get("user_id") or "",
            "filters": filters.public_dict(),
            "total_results": len(data_list),
            "new_records": new_count,
            "new_record_ids": new_ids,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"爬取失败: {exc}") from exc
