#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""api_crawler.py —— 进阶方案 A：接口逆向（requests + JSON）

两种用法：

1) 已经知道接口地址（DevTools → Network → Copy as cURL 里抠出来）：
   python api_crawler.py --api "https://example.com/api/list?page=1" --max-pages 3

2) 只知道页面地址，让脚本自己去抓接口（需要 playwright）：
   python api_crawler.py --sniff "https://example.com/news" --out result_api.csv

输出：result_api.csv（utf-8-sig，列序 title,time,author,url）
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import random

import requests

from crawler_core import (UA_POOL, walk_lists, first_key, save_csv, urljoin,
                          TITLE_KEYS, TIME_KEYS, AUTHOR_KEYS, URL_KEYS)


# ------------------------------------------------------------------ 请求
def build_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": random.choice(UA_POOL),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    return s


def fetch_json(session, url, referer=None, retries=3, timeout=10):
    """返回 (json_obj, bytes_len)；失败返回 (None, 0)。"""
    headers = {"Referer": referer} if referer else None
    for attempt in range(1, retries + 1):
        try:
            r = session.get(url, headers=headers, timeout=(6, timeout))
            if r.status_code != 200:
                print(f"  [!] HTTP {r.status_code} (第 {attempt}/{retries} 次)")
                if 400 <= r.status_code < 500 and r.status_code != 429:
                    break
            else:
                try:
                    return r.json(), len(r.content)
                except ValueError:
                    print(f"  [!] 响应不是 JSON，Content-Type={r.headers.get('content-type')}")
                    print(f"      body 前 120 字: {r.text[:120]!r}")
                    break
        except requests.RequestException as exc:
            print(f"  [!] {type(exc).__name__}: {exc} (第 {attempt}/{retries} 次)")
        if attempt < retries:
            time.sleep(2 ** attempt)
    return None, 0


# ------------------------------------------------------------------ 字段映射
def rows_from_json(data, base_url):
    best = max(walk_lists(data), key=len, default=[])
    rows, seen = [], set()
    for d in best:
        title = first_key(d, TITLE_KEYS)
        if not title:
            continue
        url = first_key(d, URL_KEYS)
        if url and not url.startswith("http"):
            url = urljoin(base_url, url)
        key = url or title
        if key in seen:
            continue
        seen.add(key)
        rows.append({"title": title,
                     "time": first_key(d, TIME_KEYS),
                     "author": first_key(d, AUTHOR_KEYS),
                     "url": url})
    return rows


def has_more(data) -> bool:
    """常见的"还有下一页"标志位。取不到就返回 True，由页数上限兜底。"""
    if isinstance(data, dict):
        for k in ("has_more", "hasMore", "hasNext", "has_next"):
            v = data.get(k)
            if isinstance(v, bool):
                return v
        for k in ("total", "totalCount", "count"):
            v = data.get(k)
            if isinstance(v, int):
                return True
        for k in ("page", "current"):
            pass
    return True


def total_count(data) -> int | None:
    if isinstance(data, dict):
        for k in ("total", "totalCount", "total_count", "count"):
            v = data.get(k)
            if isinstance(v, int):
                return v
    return None


def write_metrics(path, scheme, url, pages, rows, elapsed, total_bytes):
    if not path:
        return
    data = {
        "scheme": scheme,
        "url": url,
        "pages": pages,
        "rows": len(rows),
        "elapsed_sec": round(elapsed, 2),
        "sec_per_page": round(elapsed / max(1, pages), 2),
        "bytes_total": total_bytes,
        "missing_time": sum(1 for r in rows if not r["time"]),
        "missing_author": sum(1 for r in rows if not r["author"]),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"指标已写入 {path}")


# ------------------------------------------------------------------ 模式 1：直连接口
def run_api(api_url, out, max_pages, delay, page_param, referer, metrics_path=None):
    t0 = time.perf_counter()
    session = build_session()
    all_rows, total_bytes = [], 0

    for p in range(1, max_pages + 1):
        url = api_url if p == 1 else append_page(api_url, page_param, p)
        print(f"[页 {p}/{max_pages}] {url}")
        data, size = fetch_json(session, url, referer=referer)
        total_bytes += size
        if data is None:
            print("  [x] 本页放弃")
            continue

        rows = rows_from_json(data, api_url)
        print(f"  [✓] {size} bytes，解析 {len(rows)} 条"
              + (f"，total={total_count(data)}" if total_count(data) else ""))
        if not rows:
            print("  [i] 本页无数据，视为末页")
            break
        all_rows.extend(rows)

        if not has_more(data):
            print("  [i] has_more=false，停止翻页")
            break
        if p < max_pages:
            time.sleep(delay)

    uniq, seen = [], set()
    for r in all_rows:
        k = r["url"] or r["title"]
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)

    save_csv(uniq, out)
    elapsed = time.perf_counter() - t0
    print(f"\n成功抓取 {len(uniq)} 条 -> {out}   累计传输 {total_bytes/1024:.1f} KB")
    print(f"耗时 {elapsed:.2f}s")
    write_metrics(metrics_path, "A_api", api_url, max_pages, uniq, elapsed, total_bytes)
    return 0 if uniq else 1


def append_page(url: str, param: str, page: int) -> str:
    from urllib.parse import urlparse, urlencode, parse_qsl, urlunparse
    parts = urlparse(url)
    q = dict(parse_qsl(parts.query))
    q[param] = str(page)
    return urlunparse(parts._replace(query=urlencode(q)))


# ------------------------------------------------------------------ 模式 2：嗅探接口
def sniff(page_url, wait_ms=4000, scrolls=6):
    """打开页面，抓所有返回"列表 JSON"的 XHR，按条数排序返回。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("嗅探模式需要 playwright：\n"
                 "  uv pip install --python .venv/Scripts/python.exe playwright\n"
                 "  .venv/Scripts/python.exe -m playwright install chromium")

    hits = []

    with sync_playwright() as pw:
        browser = None
        for ch in (None, "chrome", "msedge"):
            try:
                browser = pw.chromium.launch(headless=True, channel=ch)
                print(f"[嗅探] 浏览器内核: {ch or 'bundled chromium'}")
                break
            except Exception as e:
                print(f"[!] {ch or 'bundled chromium'} 不可用: {str(e).splitlines()[0][:80]}")
        if browser is None:
            sys.exit("没有可用的浏览器内核，先执行 playwright install chromium，"
                     "或安装 Chrome/Edge 后重试")
        ctx = browser.new_context(user_agent=random.choice(UA_POOL), locale="zh-CN")
        page = ctx.new_page()

        def on_response(resp):
            ctype = (resp.headers or {}).get("content-type", "")
            if "json" not in ctype.lower():
                return
            try:
                body = resp.json()
            except Exception:
                return
            lists = list(walk_lists(body))
            if not lists:
                return
            best = max(lists, key=len)
            rows = rows_from_json(body, page_url)
            hits.append({
                "url": resp.url,
                "status": resp.status,
                "rows": rows,
                "count": len(rows),
                "headers": {k: v for k, v in (resp.request.headers or {}).items()
                            if k.lower() in ("referer", "x-requested-with", "accept",
                                             "authorization", "cookie", "x-token")},
                "raw_keys": list(best[0].keys())[:12] if best else [],
            })

        page.on("response", on_response)
        print(f"[嗅探] 打开 {page_url}")
        page.goto(page_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(wait_ms)

        for i in range(scrolls):
            page.mouse.wheel(0, 2400)
            page.wait_for_timeout(700)

        print(f"[嗅探] 命中 {len(hits)} 个返回列表的接口")
        ctx.close()
        browser.close()

    return sorted(hits, key=lambda h: -h["count"])


def run_sniff(page_url, out, delay, max_pages, page_param, metrics_path=None):
    t0 = time.perf_counter()
    hits = sniff(page_url)
    if not hits:
        print("[x] 没抓到列表接口。可能：接口非 JSON / 需要登录 / 数据在 HTML 内联。")
        return 1

    print("\n候选接口（按条数降序）:")
    for i, h in enumerate(hits[:5], 1):
        print(f"  {i}. {h['count']:>4} 条  {h['url'][:110]}")
        print(f"     字段样例: {h['raw_keys']}")

    pick = hits[0]
    print(f"\n[选用] {pick['url']}")
    session = build_session()
    session.headers.update(pick["headers"])
    session.headers.setdefault("Referer", page_url)

    all_rows, total_bytes = [], 0
    for p in range(1, max_pages + 1):
        url = pick["url"] if p == 1 else append_page(pick["url"], page_param, p)
        print(f"[复刻 页 {p}/{max_pages}] {url}")
        data, size = fetch_json(session, url, referer=page_url)
        total_bytes += size
        if data is None:
            break
        rows = rows_from_json(data, url)
        print(f"  [✓] {len(rows)} 条")
        if not rows:
            break
        all_rows.extend(rows)
        if not has_more(data):
            break
        if p < max_pages:
            time.sleep(delay)

    uniq, seen = [], set()
    for r in all_rows:
        k = r["url"] or r["title"]
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    save_csv(uniq, out)
    elapsed = time.perf_counter() - t0
    print(f"\n成功抓取 {len(uniq)} 条 -> {out}   累计传输 {total_bytes/1024:.1f} KB")
    print(f"耗时 {elapsed:.2f}s（含嗅探阶段）")
    write_metrics(metrics_path, "A_sniff", page_url, max_pages, uniq, elapsed, total_bytes)
    return 0 if uniq else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="方案 A：JSON 接口逆向采集")
    ap.add_argument("--api", help="接口地址（直接复刻）")
    ap.add_argument("--sniff", help="页面地址（自动嗅探接口）")
    ap.add_argument("-o", "--out", default="result_api.csv")
    ap.add_argument("--max-pages", type=int, default=5)
    ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument("--page-param", default="page")
    ap.add_argument("--referer", default=None)
    ap.add_argument("--metrics", default="metrics_api.json")
    a = ap.parse_args()

    if not a.api and not a.sniff:
        ap.error("必须给 --api 或 --sniff 之一")
    if a.api:
        return run_api(a.api, a.out, max(1, a.max_pages), max(1.0, a.delay),
                       a.page_param, a.referer, a.metrics)
    return run_sniff(a.sniff, a.out, max(1.0, a.delay), max(1, a.max_pages),
                     a.page_param, a.metrics)


if __name__ == "__main__":
    sys.exit(main())
