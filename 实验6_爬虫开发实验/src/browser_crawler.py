#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""browser_crawler.py —— 进阶方案 B：浏览器渲染（Playwright + Chromium）

用法:
    python browser_crawler.py https://example.com/news
    python browser_crawler.py https://example.com/news --pages 3 --selector "div.news-item"
    python browser_crawler.py https://example.com/news --headed          # 看得到浏览器
    python browser_crawler.py https://example.com/news --keep-images     # 不拦图片

输出: result_browser.csv（列序与其他方案一致，可直接 diff）
附带: metrics_browser.json（耗时 / 峰值内存 / 传输量 / 条数）
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from urllib.parse import urlparse, urlencode, parse_qsl, urlunparse

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from crawler_core import group_blocks, parse_blocks, save_csv, UA_POOL
import random

BLOCK_TYPES = {"image", "media", "font", "stylesheet"}
ITEM_WAIT = 15000          # 等条目出现
PAGE_TIMEOUT = 20000       # 单页导航超时
STABLE_ROUNDS = 2          # 连续几次滚动条数不变即认为到底


class MemorySampler:
    """后台采样本进程 + 所有子进程（chromium）的 RSS，取峰值。"""

    def __init__(self, interval=0.1):
        self.interval = interval
        self.peak = 0
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._loop, daemon=True)
        try:
            import psutil
            self.psutil = psutil
            self.proc = psutil.Process()
        except ImportError:
            self.psutil = None

    def start(self):
        if self.psutil:
            self._t.start()
        return self

    def _loop(self):
        while not self._stop.is_set():
            rss = self.proc.memory_info().rss
            for ch in self.proc.children(recursive=True):
                try:
                    rss += ch.memory_info().rss
                except Exception:
                    pass
            self.peak = max(self.peak, rss)
            time.sleep(self.interval)

    def stop(self) -> float:
        self._stop.set()
        if self.psutil and self._t.is_alive():
            self._t.join(timeout=1)
        return self.peak / 1024 / 1024


class BrowserCrawler:
    def __init__(self, pages=1, delay=2.0, selector=None, headed=False,
                 block_assets=True, max_scroll=12, channel=None, exe=None):
        self.pages = pages
        self.delay = delay
        self.selector = selector
        self.headed = headed
        self.block_assets = block_assets
        self.max_scroll = max_scroll
        self.channel = channel
        self.exe = exe
        self.bytes_total = 0
        self.rows: list[dict] = []

    # ------------------------------------------------------------ 生命周期
    def _launch(self):
        """优先用 playwright 自带 chromium；没装则退回本机 Chrome / Edge。

        自带内核要 `playwright install chromium` 下载 ~150MB，
        被网络挡住时用 channel="chrome"/"msedge" 直接驱动已安装的浏览器。
        也可以用 exe 指向手动下载解压出来的 chrome.exe。
        """
        if self.exe:
            b = self.pw.chromium.launch(headless=not self.headed, executable_path=self.exe)
            print(f"  [i] 浏览器内核: 自定义 {self.exe}")
            return b
        candidates = [self.channel] if self.channel else [None, "chrome", "msedge"]
        last = None
        for ch in candidates:
            try:
                b = self.pw.chromium.launch(headless=not self.headed, channel=ch)
                print(f"  [i] 浏览器内核: {ch or 'bundled chromium'}")
                return b
            except Exception as e:
                last = e
                print(f"  [!] {ch or 'bundled chromium'} 启动失败: {str(e).splitlines()[0][:90]}")
        raise last

    def __enter__(self):
        self.pw = sync_playwright().start()
        self.browser = self._launch()
        self.ctx = self.browser.new_context(
            user_agent=random.choice(UA_POOL),
            locale="zh-CN",
            viewport={"width": 1440, "height": 900},
        )
        if self.block_assets:
            self.ctx.route("**/*", self._router)
        self.ctx.on("response", self._count_bytes)
        return self

    def __exit__(self, *exc):
        for obj in ("ctx", "browser", "pw"):
            o = getattr(self, obj, None)
            if o is None:
                continue
            try:
                o.close() if obj != "pw" else o.stop()
            except Exception as e:
                print(f"  [!] 关闭 {obj} 时异常: {e}")
        return False

    def _router(self, route):
        if route.request.resource_type in BLOCK_TYPES:
            route.abort()
        else:
            route.continue_()

    def _count_bytes(self, resp):
        try:
            cl = resp.headers.get("content-length")
            if cl:
                self.bytes_total += int(cl)
        except Exception:
            pass

    # ------------------------------------------------------------ 渲染
    def render(self, url: str) -> str | None:
        for attempt in range(1, 3):
            page = self.ctx.new_page()
            try:
                page.set_default_timeout(PAGE_TIMEOUT)
                print(f"  [→] goto (第 {attempt}/2 次)")
                page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)

                if self.selector:
                    page.wait_for_selector(self.selector, timeout=ITEM_WAIT)
                else:
                    try:
                        page.wait_for_load_state("networkidle", timeout=5000)
                    except PWTimeout:
                        print("  [i] networkidle 超时（长连接页面常态），继续")
                    page.wait_for_timeout(1200)

                self._scroll_to_bottom(page)
                html = page.content()
                text_len = len(page.inner_text("body").strip()) if page.query_selector("body") else 0
                print(f"  [✓] 渲染完成 {len(html)} bytes DOM / 可见文本 {text_len} 字")
                return html
            except PWTimeout as e:
                print(f"  [!] 等待超时: {str(e).splitlines()[0]}")
            except Exception as e:
                print(f"  [!] {type(e).__name__}: {str(e).splitlines()[0]}")
            finally:
                page.close()
            time.sleep(2)
        return None

    def _scroll_to_bottom(self, page):
        last, stable = 0, 0
        for i in range(self.max_scroll):
            page.mouse.wheel(0, 2400)
            page.wait_for_timeout(700)
            count = len(page.query_selector_all(self.selector or "li,article,div"))
            if count == last:
                stable += 1
                if stable >= STABLE_ROUNDS:
                    print(f"  [i] 滚动 {i+1} 次后节点数稳定（{count}），停止滚动")
                    break
            else:
                stable = 0
            last = count

    # ------------------------------------------------------------ 解析
    def parse(self, html: str, base_url: str) -> list[dict]:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        blocks = soup.select(self.selector) if self.selector else group_blocks(soup)
        print(f"  [i] 条目块 {len(blocks)} 个")
        return parse_blocks(blocks, base_url)

    # ------------------------------------------------------------ 主流程
    def run(self, url: str):
        for p in range(1, self.pages + 1):
            target = url if p == 1 else append_page(url, p)
            print(f"[页 {p}/{self.pages}] {target}")
            html = self.render(target)
            if not html:
                print("  [x] 本页放弃")
                continue
            rows = self.parse(html, target)
            print(f"  [✓] 解析 {len(rows)} 条")
            self.rows.extend(rows)
            if p < self.pages:
                time.sleep(self.delay)
        return self.rows


def append_page(url: str, n: int) -> str:
    parts = urlparse(url)
    q = dict(parse_qsl(parts.query))
    q["page"] = str(n)
    return urlunparse(parts._replace(query=urlencode(q)))


def dedupe(rows):
    seen, out = set(), []
    for r in rows:
        k = r["url"] or r["title"]
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="方案 B：Playwright 渲染采集")
    ap.add_argument("url")
    ap.add_argument("-o", "--out", default="result_browser.csv")
    ap.add_argument("--pages", type=int, default=1)
    ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument("--selector", default=None)
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--keep-images", action="store_true")
    ap.add_argument("--channel", default=None, choices=["chrome", "msedge", "chromium"],
                    help="用本机已装浏览器内核（chromium 未下载时选 chrome/msedge）")
    ap.add_argument("--exe", default=os.environ.get("BROWSER_EXE"),
                    help="手动下载解压出的 chrome.exe 路径（覆盖上述所有内核选择）")
    ap.add_argument("--metrics", default="metrics_browser.json")
    a = ap.parse_args()

    sampler = MemorySampler().start()
    t0 = time.perf_counter()
    rows, bytes_total = [], 0

    with BrowserCrawler(pages=max(1, a.pages), delay=max(1.0, a.delay),
                        selector=a.selector, headed=a.headed,
                        block_assets=not a.keep_images,
                        channel=a.channel, exe=a.exe) as c:
        rows = dedupe(c.run(a.url))
        bytes_total = c.bytes_total

    elapsed = time.perf_counter() - t0
    peak = sampler.stop()
    save_csv(rows, a.out)

    metrics = {
        "scheme": "B_browser",
        "url": a.url,
        "pages": max(1, a.pages),
        "rows": len(rows),
        "elapsed_sec": round(elapsed, 2),
        "sec_per_page": round(elapsed / max(1, a.pages), 2),
        "peak_rss_mb": round(peak, 1),
        "bytes_total": bytes_total,
        "blocked_assets": not a.keep_images,
        "missing_time": sum(1 for r in rows if not r["time"]),
        "missing_author": sum(1 for r in rows if not r["author"]),
    }
    with open(a.metrics, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    print(f"\n成功抓取 {len(rows)} 条 -> {a.out}")
    print(f"耗时 {elapsed:.1f}s / 峰值内存 {peak:.0f} MB / 传输 {bytes_total/1024:.0f} KB")
    print(f"指标已写入 {a.metrics}")
    return 0 if rows else 1


if __name__ == "__main__":
    sys.exit(main())
