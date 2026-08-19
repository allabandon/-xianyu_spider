import json
import random
import string
import time
from typing import Optional, Any, Literal, Callable

import httpx
from pydantic import BaseModel
from pydantic.main import IncEx

BASE_URL = "https://h5api.m.goofish.com/h5/{}/1.0/"
APPKEY = "34839810"

client = httpx.AsyncClient(timeout=20.0)
SEARCH_API = "mtop.taobao.idlemtopsearch.pc.search"


def _dump_data(data: dict) -> str:
    return json.dumps(data, separators=(",", ":"))


def _h5_token() -> str:
    raw = client.cookies.get("_m_h5_tk")
    if not raw:
        raise RuntimeError("缺少 _m_h5_tk，无法签名搜索请求")
    return raw.split("_")[0]


class QueryParams(BaseModel):
    jsv: str = "2.7.2"
    appKey: str = APPKEY
    t: int
    sign: str
    v: str = "1.0"
    type: str = "originaljson"
    accountSite: str = "xianyu"
    dataType: str = "json"
    timeout: int = 20000
    api: str
    sessionOption: str = "AutoLoginOnly"
    spm_cnt: str
    spm_pre: Optional[str] = None

    @classmethod
    def create(cls, token: Optional[str], data: dict, api: str, spm_cnt: str, spm_pre: Optional[str] = None):
        if not token:
            token = "undefined"
        t = int(time.time() * 1000)
        sign = generate_sign(token, APPKEY, data, t)
        return cls(t=t, api=api, spm_cnt=spm_cnt, spm_pre=spm_pre, sign=sign)

    def model_dump(
            self,
            *,
            mode: Literal['json', 'python'] | str = 'python',
            include: IncEx | None = None,
            exclude: IncEx | None = None,
            context: Any | None = None,
            by_alias: bool | None = None,
            exclude_unset: bool = False,
            exclude_defaults: bool = False,
            exclude_none: bool = True,
            round_trip: bool = False,
            warnings: bool | Literal['none', 'warn', 'error'] = True,
            fallback: Callable[[Any], Any] | None = None,
            serialize_as_any: bool = False,
    ) -> dict[str, Any]:
        return super().model_dump(mode=mode, include=include, exclude=exclude, context=context,
                                  by_alias=by_alias, exclude_unset=exclude_unset,
                                  exclude_defaults=exclude_defaults, exclude_none=True & exclude_none,
                                  round_trip=round_trip, warnings=warnings, fallback=fallback,
                                  serialize_as_any=serialize_as_any)


async def init():
    client.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"})
    # A cookie used to trace user behavior, thus can be randomly generated
    client.cookies.update({
        'cna': "".join(random.choices(string.ascii_letters + string.digits, k=25)),
    })
    await client.get("https://www.goofish.com/")
    await init_h5tk()
    if not client.cookies.get("_m_h5_tk"):
        raise RuntimeError("初始化闲鱼 token 失败")


async def init_h5tk():
    """
    Initialize the _m_h5_tk cookie by making a request to the announcement page.
    The _m_h5_tk cookie is required for authenticated API requests.
    """
    data = {"piUrl": "https://h5.m.goofish.com/wow/moyu/moyu-project/xy-site/pages/announcement"}
    qp = QueryParams.create(token=None, data=data, api="mtop.gaia.nodejs.gaia.idle.data.gw.v2.index.get",
                            spm_cnt="a21ybx.home.0.0")
    response = await client.post(
        BASE_URL.format("mtop.gaia.nodejs.gaia.idle.data.gw.v2.index.get"),
        params=qp.model_dump(),
        data={"data": _dump_data(data)},
    )
    response.raise_for_status()


def generate_sign(token: str, appkey: str, data: dict, j: int):
    """
    Generate the sign parameter for the API request.

    sign = md5(d.token + "&" + j + "&" + h + "&" + c.data)
    j = (new Date).getTime()
    h = appkey
    """
    import hashlib
    data = json.dumps(data, separators=(',', ':'))
    h = appkey
    sign_str = f"{token}&{j}&{h}&{data}"
    sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest()
    return sign


async def search(keyword: str, page: int = 1):
    # 对齐原版 Playwright 点击「新发布 / 最新」后的请求体
    data = {
        "pageNumber": page,
        "keyword": keyword,
        "fromFilter": True,
        "rowsPerPage": 30,
        "sortValue": "desc",
        "sortField": "create",
        "customDistance": "",
        "gps": "",
        "propValueStr": {"searchFilter": ""},
        "customGps": "",
        "searchReqFromPage": "pcSearch",
        "extraFilterValue": "{}",
        "userPositionJson": "{}",
    }
    data_final = _dump_data(data)
    url = BASE_URL.format(SEARCH_API)
    qp = QueryParams.create(
        token=_h5_token(),
        data=data,
        api=SEARCH_API,
        spm_cnt="a21ybx.search.0.0",
        spm_pre="a21ybx.search.searchInput.0",
    )
    response = await client.post(url, params=qp.model_dump(), data={"data": data_final})
    response.raise_for_status()
    result = response.json()
    ret = result.get("ret") or []
    if not any(str(item).startswith("SUCCESS") for item in ret):
        raise RuntimeError(f"搜索接口调用失败: {ret}")
    return result
