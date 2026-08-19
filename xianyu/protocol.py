"""闲鱼登录辅助：Cookie 解析、扫码状态、终端二维码。"""

from __future__ import annotations

import base64
from typing import Any
from urllib.parse import parse_qsl, unquote, urlparse


def parse_cookie_header(cookie: str) -> dict[str, str]:
    """把浏览器复制的 Cookie 字符串解析成字典。"""
    result: dict[str, str] = {}
    if not cookie:
        return result
    for part in cookie.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        name = name.strip()
        if not name:
            continue
        result[name] = value.strip()
    return result


def dump_cookie_header(cookies: dict[str, str]) -> str:
    return "; ".join(f"{name}={value}" for name, value in cookies.items() if name)


LOGIN_COOKIE_NAMES = (
    "sgcookie",
    "sgcookie",
    "csg",
    "lgc",
    "havana-lgc0",
    "havana-lgc1",
)

# fancyboi999/goofish-cli 同款：这三个齐了才算网页扫码登录完成。
OFFICIAL_SESSION_COOKIE_NAMES = ("_m_h5_tk", "unb", "cookie2")

COOKIE_QUERY_ALIAS = {
    "unb": "unb",
    "unb": "unb",
    "uid": "unb",
    "userid": "unb",
    "cookie2": "cookie2",
    "cookie2": "cookie2",
    "cookie1": "cookie1",
    "sgcookie": "sgcookie",
    "sgcookie": "sgcookie",
    "_tb_token_": "_tb_token_",
    "tracknick": "tracknick",
    "_nk_": "_nk_",
    "csg": "csg",
    "lgc": "lgc",
    "havana-lgc0": "havana-lgc0",
    "havana-lgc1": "havana-lgc1",
    "cookie17": "cookie17",
    "wk_cookie2": "wk_cookie2",
    "wk_unb": "wk_unb",
    "_m_h5_tk": "_m_h5_tk",
    "_m_h5_tk_enc": "_m_h5_tk_enc",
    "sn": "sn",
}

RISK_VERIFY_MARKERS = (
    "havana",
    "/iv/",
    "/iv?",
    "verify.htm",
    "verify.html",
    "/verify",
    "punish",
    "h5_verify",
    "identity",
    "aq.taobao",
    "baxia",
    "dialog/view",
    "risk",
)


def cookie_user_id(cookies: dict[str, str]) -> str:
    for key in ("unb", "unb", "userid", "user_id", "uid"):
        value = str(cookies.get(key) or "").strip()
        if value:
            return value
    sn = str(cookies.get("sn") or "").strip()
    if sn.isdigit():
        return sn
    return ""


def has_login_cookies(cookies: dict[str, str]) -> bool:
    """判断 jar 里是否已有闲鱼登录态（不只看 unb）。"""
    if cookie_user_id(cookies):
        return True
    return any(str(cookies.get(name) or "").strip() for name in LOGIN_COOKIE_NAMES)


def has_official_session_cookies(cookies: dict[str, str]) -> bool:
    """官方登录页扫码成功：`_m_h5_tk` + `unb` + `cookie2` 必须齐全。"""
    return all(str((cookies or {}).get(name) or "").strip() for name in OFFICIAL_SESSION_COOKIE_NAMES)


def cookies_from_query_url(url: str) -> dict[str, str]:
    """从 passport 异步种 Cookie 的 URL query 里抽出登录 Cookie。"""
    if not url or not isinstance(url, str):
        return {}
    try:
        parsed = urlparse(url)
    except Exception:
        return {}
    pairs = list(parse_qsl(parsed.query, keep_blank_values=False))
    fragment = parsed.fragment or ""
    if "=" in fragment:
        if "?" in fragment:
            fragment = fragment.split("?", 1)[1]
        pairs.extend(parse_qsl(fragment, keep_blank_values=False))
    result: dict[str, str] = {}
    for name, value in pairs:
        mapped = COOKIE_QUERY_ALIAS.get(name) or COOKIE_QUERY_ALIAS.get(name.lower())
        if mapped and value:
            result[mapped] = unquote(value)
    return result


def is_iv_check_login_url(url: str) -> bool:
    """拍脸成功后的回调页 ivCheckLogin.htm。核身页 verify.htm 即使带 havana_iv_token 也不是回调。"""
    text = (url or "").lower()
    compact = text.replace("_", "").replace("-", "")
    return "ivchecklogin" in compact


def is_risk_verify_url(url: str) -> bool:
    if is_iv_check_login_url(url):
        return False
    text = (url or "").lower()
    return bool(text) and any(marker in text for marker in RISK_VERIFY_MARKERS)


def is_identity_qr_page(url: str) -> bool:
    """官方核身页（拍摄脸部）自己带二维码，不能再把页面链接画成码去扫。"""
    return is_risk_verify_url(url) and not is_iv_check_login_url(url)


FACE_VERIFY_HINT = (
    "官方是「拍摄脸部」核身，验证页自己带二维码。"
    "不要扫验证页链接生成的码（手机会再打开同一页，变成套娃）。"
    "终端登录会自动用 Playwright 打开核身页；请在弹出窗口里扫码并拍脸。"
    "登录二维码变成 expired 是正常的，不要重新生成。"
)


def is_login_success_url(url: str) -> bool:
    text = (url or "").lower()
    if not text:
        return False
    if is_iv_check_login_url(text):
        return True
    if is_risk_verify_url(text):
        return False
    return any(host in text for host in ("goofish.com", "taobao.com", "tmall.com", "alipay.com"))


def collect_async_urls(data: dict) -> list[str]:
    """收集官方用来同步种 Cookie 的 asyncUrls / st 地址。"""
    urls: list[str] = []
    if not isinstance(data, dict):
        return urls
    for key, val in data.items():
        compact = str(key).replace("_", "").lower()
        if compact not in {"asyncurls", "sturl", "sturls", "syncurls"}:
            continue
        candidates = val if isinstance(val, list) else [val]
        for item in candidates:
            text = str(item or "").strip()
            if text.startswith("http"):
                urls.append(text)
    seen: set[str] = set()
    unique: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


def passport_flag(data: dict, *names: str) -> Any:
    """按字段名大小写不敏感取值。"""
    if not isinstance(data, dict):
        return None
    lowered = {str(key).lower(): value for key, value in data.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value not in (None, ""):
            return value
    return None


def normalize_qr_status(status: str) -> str:
    """闲鱼官方状态是 NEW / SCANED（一个 N）/ CONFIRMED / EXPIRED / CANCELED。"""
    raw = (status or "").strip()
    key = raw.upper().replace("-", "_")
    mapping = {
        "NEW": "new",
        "WAIT": "new",
        "WAITING": "new",
        "SCAN": "scanned",
        "SCANED": "scanned",
        "SCANNED": "scanned",
        "CONFIRMED": "confirmed",
        "SUCCESS": "confirmed",
        "PASSED": "confirmed",
        "OK": "confirmed",
        "EXPIRED": "expired",
        "EXPIRE": "expired",
        "CANCELED": "canceled",
        "CANCELLED": "canceled",
    }
    return mapping.get(key, raw.lower() or "new")


def is_qr_confirmed(status: str) -> bool:
    return normalize_qr_status(status) == "confirmed"


def qr_status_hint(status: str) -> str:
    mapped = normalize_qr_status(status)
    hints = {
        "new": "等待扫描，请用闲鱼 App 扫码。",
        "scanned": "已扫码，请在闲鱼 App 里点「确认登录」。只扫码不会登录。",
        "confirmed": "已在 App 确认，正在换取登录 Cookie。",
        "expired": "二维码已过期，请重新调用 POST /auth/qr/start。",
        "canceled": "已取消登录，请重新生成二维码。",
    }
    return hints.get(mapped, f"当前状态: {mapped}")


def _qr_code(content: str, *, border: int = 2):
    import qrcode

    text = (content or "").strip()
    if not text:
        return None
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=8,
        border=border,
    )
    qr.add_data(text)
    qr.make(fit=True)
    return qr


def qr_png_base64(content: str) -> str:
    """把任意文本（登录码或验证链接）画成 PNG 二维码。"""
    try:
        qr = _qr_code(content, border=2)
        if qr is None:
            return ""
        import io

        image = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("ascii")
    except Exception:
        return ""


def qr_ascii(content: str, *, invert: bool = True) -> str:
    """把任意文本画成终端可扫描的 Unicode 二维码。invert=True 适合深色背景。"""
    try:
        qr = _qr_code(content, border=1)
        if qr is None:
            return ""
        import io

        buffer = io.StringIO()
        qr.print_ascii(out=buffer, invert=invert)
        return buffer.getvalue().rstrip() + "\n"
    except Exception:
        return ""

