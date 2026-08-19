import asyncio
import hashlib
import os
import traceback
from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from tortoise import Model, fields
from tortoise.contrib.fastapi import register_tortoise

from api import init, search

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init()
    yield


# 初始化FastAPI应用
app = FastAPI(title="闲鱼商品搜索API", description="支持并发请求的闲鱼商品搜索接口", lifespan=lifespan)


def get_md5(text: str) -> str:
    """返回给定文本的MD5哈希值"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def get_link_unique_key(link: str) -> str:
    """
    截取链接中前1个"&"之前的内容作为唯一标识依据。
    如果链接中的"&"少于1个，则返回整个链接。
    """
    # 尝试拆分链接，最多拆分1次
    parts = link.split('&', 1)
    if len(parts) >= 2:
        # 拼接前1部分，保留"&"连接符
        return '&'.join(parts[:1])
    else:
        return link


# 定义数据库模型，增加 link_hash 字段用于唯一性判断
class XianyuProduct(Model):
    id = fields.IntField(pk=True)
    title = fields.TextField(description="商品标题")
    price = fields.CharField(max_length=50, description="当前售价")
    area = fields.CharField(max_length=100, description="发货地区")
    seller = fields.CharField(max_length=100, description="卖家昵称")
    # 存储完整链接，不设置唯一性约束
    link = fields.TextField(description="商品链接", column_type="MEDIUMTEXT")
    # 使用 link_hash 字段保存截取后的链接 MD5 值，并设置唯一约束
    link_hash = fields.CharField(max_length=32, unique=True, description="商品链接哈希")
    image_url = fields.TextField(description="商品图片链接", column_type="MEDIUMTEXT")
    publish_time = fields.DatetimeField(null=True, description="发布时间")

    class Meta:
        table = "xianyu_products"


# 配置数据库
DATABASE_URL = os.environ.get("DATABASE_URL")
DATABASE_CONFIG = {
    "connections": {
        "default": DATABASE_URL
    },
    "apps": {
        "models": {
            "models": ["__main__"],
            "default_connection": "default",
        }
    }
}

register_tortoise(
    app,
    config=DATABASE_CONFIG,
    generate_schemas=True,  # 自动创建表结构
    add_exception_handlers=True,
)


async def safe_get(data, *keys, default="暂无"):
    """安全获取嵌套字典值"""
    for key in keys:
        try:
            data = data[key]
        except (KeyError, TypeError, IndexError):
            return default
    return data


async def save_to_db(data_list):
    """
    逐条保存数据到数据库，若相同链接（按截取规则判断）的记录已存在则跳过，
    同时统计当前关键词下新增的记录数量，并返回新增记录的 id 列表
    """
    new_records = 0
    new_ids = []
    for item in data_list:
        try:
            link = item["商品链接"]
            # 先截取链接内容
            unique_part = get_link_unique_key(link)
            # 计算唯一标识的 MD5 哈希值
            link_hash = get_md5(unique_part)
            product, created = await XianyuProduct.get_or_create(
                link_hash=link_hash,
                defaults={
                    "title": item["商品标题"],
                    "price": item["当前售价"],
                    "area": item["发货地区"],
                    "seller": item["卖家昵称"],
                    "link": link,
                    "image_url": item["商品图片链接"],
                    "publish_time": datetime.strptime(item["发布时间"], "%Y-%m-%d %H:%M")
                    if item["发布时间"] != "未知时间" else None,
                }
            )
            if created:
                new_records += 1
                new_ids.append(product.id)
        except Exception as e:
            print(f"保存数据出错: {str(e)}")
    return new_records, new_ids


async def handle_data(data: dict):
    if str(data).find("NoneOfResult") != -1:
        return []
    items = data.get("data", {}).get("resultList") or []
    res = []
    for item in items:
        main_data = await safe_get(item, "data", "item", "main", "exContent", default={})
        click_params = await safe_get(item, "data", "item", "main", "clickParam", "args", default={})

        # 解析商品信息
        title = await safe_get(main_data, "title", default="未知标题")

        # 价格处理
        price_parts = await safe_get(main_data, "price", default=[])
        price = "价格异常"
        if isinstance(price_parts, list):
            price = "".join([str(p.get("text", "")) for p in price_parts if isinstance(p, dict)])
            price = price.replace("当前价", "").strip()
            if "万" in price:
                price = f"¥{float(price.replace('¥', '').replace('万', '')) * 10000:.0f}"
        # 其他字段解析
        area = await safe_get(main_data, "area", default="地区未知")
        seller = await safe_get(main_data, "userNickName", default="匿名卖家")
        raw_link = await safe_get(item, "data", "item", "main", "targetUrl", default="")
        image_url = await safe_get(main_data, "picUrl", default="")

        res.append({
            "商品标题": title,
            "当前售价": price,
            "发货地区": area,
            "卖家昵称": seller,
            "商品链接": raw_link.replace("fleamarket://", "https://www.goofish.com/"),
            "商品图片链接": f"https:{image_url}" if image_url and not image_url.startswith(
                "http") else image_url,
            "发布时间": datetime.fromtimestamp(
                int(click_params.get("publishTime", 0)) / 1000
            ).strftime("%Y-%m-%d %H:%M") if click_params.get("publishTime", "").isdigit() else "未知时间"
        })
    return res


async def scrape_xianyu_http(keyword: str, max_pages: int = 1):
    semaphore = asyncio.Semaphore(3)

    async def fetch_page(page: int):
        async with semaphore:
            return page, await handle_data(await search(keyword, page))

    gathered = await asyncio.gather(*[fetch_page(page) for page in range(1, max_pages + 1)])
    res = []
    for _, items in sorted(gathered, key=lambda item: item[0]):
        res.extend(items)
    return res


@app.post("/search/", summary="商品搜索接口",
          description="接收搜索关键词和页数，返回爬取结果数量、新增记录数量及新增记录的id列表")
async def search_items(keyword: str, max_pages: int = 1):
    """
    参数：
    - keyword: 搜索关键词（必需）
    - max_pages: 最大爬取页数（默认1）
    """
    try:
        data_list = await scrape_xianyu_http(keyword, max_pages)

        # 保存数据并统计新增记录数，同时返回新增记录的id列表
        new_count, new_ids = (0, [])
        if data_list:
            new_count, new_ids = await save_to_db(data_list)

        return {
            "status": "success",
            "keyword": keyword,
            "total_results": len(data_list),
            "new_records": new_count,
            "new_record_ids": new_ids
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"爬取失败: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
