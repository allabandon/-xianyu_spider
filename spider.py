"""启动入口：python spider.py [serve|login|search]"""

from xianyu.app import app


def main(argv: list[str] | None = None) -> None:
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="闲鱼 HTTP 接口")
    parser.add_argument(
        "command",
        nargs="?",
        default="serve",
        choices=["serve", "login", "search"],
        help="serve 启动 API；login 登录；search 命令行抓取",
    )
    parser.add_argument("keyword", nargs="?", default=None, help="search 的关键词")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--cookie",
        nargs="?",
        const="-",
        default=None,
        help="粘贴网页 Cookie 登录；不跟值则从终端读入",
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="与默认 login 相同：终端画登录码（兼容旧参数）",
    )
    parser.add_argument(
        "--browser",
        action="store_true",
        help="直接打开官方登录页扫码，不先画终端码",
    )
    parser.add_argument("--timeout", type=int, default=180, help="拍脸/官方页扫码等待秒数")
    parser.add_argument("--pages", type=int, default=1, help="search 抓取页数")
    parser.add_argument(
        "--sort",
        default="newest",
        choices=["newest", "price_asc", "price_desc", "default"],
        help="search 排序，默认 newest",
    )
    parser.add_argument("--min-price", type=int, default=None, help="最低价格（元）")
    parser.add_argument("--max-price", type=int, default=None, help="最高价格（元）")
    parser.add_argument("--province", default=None, help="省份，如 广东")
    parser.add_argument("--city", default=None, help="城市，如 深圳")
    parser.add_argument("--days", type=int, default=None, help="最近几天发布")
    parser.add_argument("--no-save", action="store_true", help="只打印结果，不写入数据库")
    args = parser.parse_args(argv)
    if args.command == "login":
        from xianyu.cli import run_login

        if args.cookie is not None:
            mode = "cookie"
        elif args.browser:
            mode = "browser"
        else:
            mode = "qr"
        raise SystemExit(
            asyncio.run(
                run_login(mode=mode, cookie=args.cookie or "", timeout=args.timeout)
            )
        )
    if args.command == "search":
        from xianyu.cli import run_search

        raise SystemExit(
            asyncio.run(
                run_search(
                    keyword=args.keyword or "",
                    pages=args.pages,
                    sort=args.sort,
                    min_price=args.min_price,
                    max_price=args.max_price,
                    province=args.province,
                    city=args.city,
                    publish_days=args.days,
                    save=not args.no_save,
                )
            )
        )

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
