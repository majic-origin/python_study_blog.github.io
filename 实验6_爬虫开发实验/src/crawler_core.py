#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""crawl.py —— 给一个 URL 就直接抓取列表页并产出 CSV 的单文件爬虫。

用法:
    python crawl.py https://example.com/news
    python crawl.py https://example.com/news -o news.csv --pages 3 --delay 2.5
    python crawl.py https://example.com/news --selector "div.item"   # 手动指定条目选择器

设计目标: 不做站点硬编码，靠"结构分组 + 字段正则"的启发式自动找列表。
失败时不猜，直接把诊断信息打出来（HTML 长度、候选分组、前 500 字文本）。
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from urllib.parse import urljoin, urlparse, urlencode, parse_qsl, urlunparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("缺少依赖: pip install requests beautifulsoup4 lxml")

UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

TIME_PATTERNS = [
    re.compile(r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?"),
    re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}"),
    re.compile(r"\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2}"),
    re.compile(r"\d{1,2}\s*(?:分钟|小时|天)前"),
]
AUTHOR_PATTERNS = [
    re.compile(r"(?:作者|撰文|记者|来源|编辑|发布者)\s*[:：]\s*([^\s|｜/，,]{2,14})"),
    re.compile(r"文\s*[/／]\s*([^\s|｜，,]{2,14})"),
]


# ---------------------------------------------------------------- 请求层
def build_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": random.choice(UA_POOL),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    })
    return s


def fetch(session: requests.Session, url: str, retries: int = 3, timeout: int = 10) -> str | None:
    for attempt in range(1, retries + 1):
        try:
            r = session.get(url, timeout=(6, timeout))
            if r.status_code != 200:
                print(f"  [!] HTTP {r.status_code} (第 {attempt}/{retries} 次)")
                if 400 <= r.status_code < 500 and r.status_code != 429:
                    return None                      # 4xx 不重试
            else:
                if r.encoding in (None, "ISO-8859-1"):
                    r.encoding = r.apparent_encoding or "utf-8"
                print(f"  [✓] 200  {len(r.content)} bytes  encoding={r.encoding}")
                return r.text
        except requests.RequestException as exc:
            print(f"  [!] {type(exc).__name__}: {exc} (第 {attempt}/{retries} 次)")
        if attempt < retries:
            time.sleep(2 ** attempt)                 # 2s / 4s / 8s
    return None


# ---------------------------------------------------------------- 结构分组
def group_blocks(soup: BeautifulSoup):
    """把页面里"长得一样、重复出现、带链接"的节点分组，返回最大候选组。"""
    groups: dict[tuple, list] = defaultdict(list)
    for tag in soup.find_all(["li", "div", "article", "section", "tr"]):
        anchor = tag.find("a", href=True)
        if not anchor:
            continue
        cls = " ".join(sorted(tag.get("class") or []))
        groups[(tag.name, cls)].append(tag)

    best, best_score = None, 0.0
    for (name, cls), nodes in groups.items():
        if len(nodes) < 3:
            continue
        anchors = [n.find("a", href=True) for n in nodes]
        texty = sum(1 for a in anchors if a and len(a.get_text(strip=True)) >= 4)
        if texty < len(nodes) * 0.6:
            continue
        score = len(nodes) * (1.0 if cls else 0.45)
        if score > best_score:
            best, best_score = nodes, score
    return best or []


# ---------------------------------------------------------------- 字段提取
def pick_title(block) -> tuple[str, str]:
    heads = block.find_all(["h1", "h2", "h3", "h4", "h5", "a"])
    best, best_len = "", 0
    for h in heads:
        txt = re.sub(r"\s+", " ", h.get_text(strip=True))
        if len(txt) > best_len:
            best, best_len = txt, len(txt)
    link = block.find("a", href=True)
    for h in heads:
        if h.name == "a" and h.get("href") and len(h.get_text(strip=True)) >= 4:
            link = h
            break
    return best, (link.get("href") if link else "")


def pick_time(text: str) -> str:
    for pat in TIME_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        raw = m.group(0)
        m2 = re.match(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", raw)
        if m2:
            y, mo, d = m2.groups()
            try:
                return datetime(int(y), int(mo), int(d)).strftime("%Y-%m-%d")
            except ValueError:
                return raw
        return raw
    return ""


def pick_author(text: str) -> str:
    for pat in AUTHOR_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(1)
    return ""


def parse_blocks(blocks, base_url: str) -> list[dict]:
    rows, seen = [], set()
    for b in blocks:
        text = re.sub(r"[ \t\u3000]+", " ", b.get_text(" ", strip=True))
        title, href = pick_title(b)
        if not title or len(title) < 2:
            continue
        url = urljoin(base_url, href) if href else ""
        key = url or title
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "title": title,
            "time": pick_time(text),
            "author": pick_author(text),
            "url": url,
        })
    return rows


# ---------------------------------------------------------------- 内联 JSON 兜底
STATE_MARKERS = ["__INITIAL_STATE__", "__NUXT__", "__NEXT_DATA__", "__APOLLO_STATE__", "window.__DATA__"]
TITLE_KEYS = ("title", "titleText", "name", "headline", "subject")
TIME_KEYS = ("publishTime", "pubDate", "publish_time", "date", "createTime", "time")
AUTHOR_KEYS = ("author", "authorName", "source", "media", "byline")
URL_KEYS = ("url", "link", "detailUrl", "href", "articleUrl")


def extract_inline_json(html: str):
    dec = json.JSONDecoder()
    for marker in STATE_MARKERS:
        idx = html.find(marker)
        while idx != -1:
            brace = html.find("{", idx)
            if brace != -1:
                try:
                    obj, _ = dec.raw_decode(html[brace:])
                    return obj
                except json.JSONDecodeError:
                    pass
            idx = html.find(marker, idx + 1)
    return None


def walk_lists(obj, depth=0):
    if depth > 12:
        return
    if isinstance(obj, list):
        dicts = [x for x in obj if isinstance(x, dict)]
        if len(dicts) >= 3 and any(any(k in d for k in TITLE_KEYS) for d in dicts):
            yield dicts
        for x in obj[:200]:
            yield from walk_lists(x, depth + 1)
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from walk_lists(v, depth + 1)


def first_key(d: dict, keys) -> str:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, (int, float)) and k in TIME_KEYS:
            try:
                ts = v / 1000 if v > 1e11 else v
                return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            except (OSError, ValueError):
                return str(v)
    return ""


def rows_from_json(data, base_url: str) -> list[dict]:
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
        rows.append({"title": title, "time": first_key(d, TIME_KEYS),
                     "author": first_key(d, AUTHOR_KEYS), "url": url})
    return rows


# ---------------------------------------------------------------- 翻页
def page_url(base: str, n: int) -> str:
    parts = urlparse(base)
    q = dict(parse_qsl(parts.query))
    q["page"] = str(n)
    return urlunparse(parts._replace(query=urlencode(q)))


# ---------------------------------------------------------------- 主流程
def save_csv(rows: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["title", "time", "author", "url"])
        w.writeheader()
        w.writerows(rows)


def crawl(url: str, pages: int, delay: float, selector: str | None, out: str) -> int:
    session = build_session()
    all_rows: list[dict] = []

    for p in range(1, pages + 1):
        target = url if p == 1 else page_url(url, p)
        print(f"[页 {p}/{pages}] {target}")
        html = fetch(session, target)
        if not html:
            print("  [x] 本页放弃")
            continue

        soup = BeautifulSoup(html, "lxml")
        visible = soup.get_text(strip=True)
        print(f"  可见文本 {len(visible)} 字 / <script> {len(soup.find_all('script'))} 个")

        blocks = soup.select(selector) if selector else group_blocks(soup)
        print(f"  候选条目块 {len(blocks)} 个" + (f"（选择器 {selector}）" if selector else "（启发式分组）"))
        rows = parse_blocks(blocks, target)

        if len(rows) < 3:
            data = extract_inline_json(html)
            if data is not None:
                jrows = rows_from_json(data, target)
                print(f"  [i] 内联 JSON 命中，解析出 {len(jrows)} 条")
                if len(jrows) > len(rows):
                    rows = jrows

        if not rows:
            print("  [x] 未解析出数据。诊断:")
            print("      · 可见文本前 300 字:", visible[:300].replace("\n", " "))
            print("      · 若上方文本很少 → 页面由 JS 渲染，需浏览器方案:")
            print("        pip install playwright && playwright install chromium")
            print("        python -c \"from playwright.sync_api import sync_playwright as s;"
                  "\n        p=s().start();b=p.chromium.launch();pg=b.new_page();pg.goto(URL);"
                  "print(pg.content())\"")
            print("      · 也可手动指定条目容器: --selector \"div.news-item\"")
        else:
            print(f"  [✓] 解析 {len(rows)} 条，示例: {rows[0]['title'][:30]}")
            all_rows.extend(rows)

        if p < pages:
            time.sleep(delay)

    # 去重（按 url，其次 title）
    seen, uniq = set(), []
    for r in all_rows:
        k = r["url"] or r["title"]
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)

    save_csv(uniq, out)
    print(f"\n成功抓取 {len(uniq)} 条 -> {out}")
    if uniq:
        miss = {f: sum(1 for r in uniq if not r[f]) for f in ("time", "author")}
        print(f"字段缺失统计: 时间 {miss['time']} 条 / 作者 {miss['author']} 条")
    return 0 if uniq else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="给一个列表页 URL，自动抓取标题/时间/作者/链接")
    ap.add_argument("url", help="列表页 URL")
    ap.add_argument("-o", "--out", default="result.csv", help="输出 CSV（默认 result.csv）")
    ap.add_argument("--pages", type=int, default=1, help="翻页数，默认 1；按 ?page=n 追加参数")
    ap.add_argument("--delay", type=float, default=2.0, help="翻页间隔秒，默认 2.0")
    ap.add_argument("--selector", default=None, help="手动指定条目容器 CSS 选择器")
    a = ap.parse_args()
    return crawl(a.url, max(1, a.pages), max(1.0, a.delay), a.selector, a.out)


if __name__ == "__main__":
    sys.exit(main())
