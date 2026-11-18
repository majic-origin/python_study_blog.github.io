#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""metrics.py —— 双方案同口径测量与对比表生成

用法:
    python metrics.py --page-url http://127.0.0.1:8899/spa_live.html \
                      --api "http://127.0.0.1:8899/api/list.json?page=1" \
                      --pages 1 --rounds 3

做什么:
    1. 依次跑 方案A(接口) / 方案B(渲染)，各跑 N 轮；
    2. 每轮独立子进程，测墙钟耗时与子进程树 RSS 峰值；
    3. 取中位数，写 metrics_raw.json，再生成 compare.md 对比表。

为什么用子进程:
    同进程内测两种方案会互相污染（浏览器残留、连接池、GC 状态），
    只有每次冷启动的结果才有对比意义。
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent      # src/
ROOT = HERE.parent                          # 实验根目录
PY = sys.executable


# ------------------------------------------------------------------ 测量
def run_once(cmd: list[str], log_path: Path) -> dict:
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    t0 = time.perf_counter()
    proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", env=env)
    lines: list[str] = []

    def reader():
        for line in proc.stdout:
            lines.append(line.rstrip())

    th = threading.Thread(target=reader, daemon=True)
    th.start()

    peak = 0
    try:
        me = psutil.Process(proc.pid)
    except psutil.NoSuchProcess:
        me = None

    while proc.poll() is None:
        if me is not None:
            try:
                rss = me.memory_info().rss
                for ch in me.children(recursive=True):
                    try:
                        rss += ch.memory_info().rss
                    except psutil.Error:
                        pass
                peak = max(peak, rss)
            except psutil.Error:
                pass
        time.sleep(0.08)

    th.join(timeout=5)
    elapsed = time.perf_counter() - t0
    log_path.write_text("\n".join(lines), encoding="utf-8")
    return {"sec": round(elapsed, 2), "peak_mb": round(peak / 1024 / 1024, 1),
            "rc": proc.returncode, "tail": lines[-3:]}


def csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with open(path, encoding="utf-8-sig") as f:
        return max(0, sum(1 for _ in f) - 1)


def loc(path: Path) -> int:
    """有效代码行：去空行、去纯注释行、去文档字符串引号行。"""
    if not path.exists():
        return 0
    n = 0
    for ln in path.read_text(encoding="utf-8").splitlines():
        s = ln.strip()
        if not s or s.startswith("#") or s.startswith('"""') or s.startswith("'''"):
            continue
        n += 1
    return n


# ------------------------------------------------------------------ 方案定义
def build_schemes(a):
    schemes = []
    api_metrics = Path(a.out_dir) / "metrics_api.json"
    if a.api:
        schemes.append({
            "key": "A_api",
            "label": "A 接口逆向",
            "script": "api_crawler.py",
            "csv": Path(a.out_dir) / "result_api.csv",
            "metrics": api_metrics,
            "cmd": [PY, str(HERE / "api_crawler.py"), "--api", a.api, "--max-pages", str(a.pages),
                    "--delay", "1.5", "-o", str(Path(a.out_dir) / "result_api.csv"),
                    "--metrics", str(api_metrics)],
        })
    elif a.page_url:
        schemes.append({
            "key": "A_sniff",
            "label": "A 接口嗅探（含浏览器启动）",
            "script": "api_crawler.py",
            "csv": Path(a.out_dir) / "result_api.csv",
            "metrics": api_metrics,
            "cmd": [PY, str(HERE / "api_crawler.py"), "--sniff", a.page_url, "--max-pages", str(a.pages),
                    "--delay", "1.5", "-o", str(Path(a.out_dir) / "result_api.csv"),
                    "--metrics", str(api_metrics)],
        })

    schemes.append({
        "key": "B_browser",
        "label": "B 浏览器渲染",
        "script": "browser_crawler.py",
        "csv": Path(a.out_dir) / "result_browser.csv",
        "metrics": Path(a.out_dir) / "metrics_browser.json",
        "cmd": [PY, str(HERE / "browser_crawler.py"), a.page_url, "--pages", str(a.pages),
                "--delay", "1.5", "-o", str(Path(a.out_dir) / "result_browser.csv"),
                "--metrics", str(Path(a.out_dir) / "metrics_browser.json")],
    })
    return schemes


def main() -> int:
    ap = argparse.ArgumentParser(description="双方案测量与对比")
    ap.add_argument("--page-url", required=True, help="列表页地址（方案 B 用）")
    ap.add_argument("--api", default=None, help="接口地址（方案 A 直连；不给则用嗅探模式）")
    ap.add_argument("--pages", type=int, default=1)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--out-dir", default="_metrics")
    ap.add_argument("--raw", default="metrics_raw.json")
    ap.add_argument("--report", default="compare.md")
    a = ap.parse_args()

    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "page_url": a.page_url, "api": a.api,
           "pages": a.pages, "rounds": a.rounds, "schemes": {}}

    for s in build_schemes(a):
        print(f"\n===== {s['label']} =====")
        runs = []
        for i in range(1, a.rounds + 1):
            log = out_dir / f"{s['key']}_r{i}.log"
            print(f"  第 {i}/{a.rounds} 轮 ...", end="", flush=True)
            r = run_once(s["cmd"], log)
            r["rows"] = csv_rows(s["csv"])
            runs.append(r)
            print(f" {r['sec']}s / {r['peak_mb']}MB / {r['rows']} 条 / rc={r['rc']}")

        secs = [r["sec"] for r in runs]
        peaks = [r["peak_mb"] for r in runs]
        ok = sum(1 for r in runs if r["rc"] == 0 and r["rows"] > 0)

        extra = {}
        if s["metrics"] and s["metrics"].exists():
            try:
                extra = json.loads(s["metrics"].read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass

        raw["schemes"][s["key"]] = {
            "label": s["label"],
            "runs": runs,
            "median_sec": round(statistics.median(secs), 2),
            "median_peak_mb": round(statistics.median(peaks), 1),
            "sec_per_page": round(statistics.median(secs) / max(1, a.pages), 2),
            "rows": runs[0]["rows"] if runs else 0,
            "stability": f"{ok}/{a.rounds}",
            "bytes_total": extra.get("bytes_total"),
            "loc": loc(HERE / s["script"]),
            "deps": "requests, beautifulsoup4, lxml" if s["script"].startswith("api")
                    else "playwright, beautifulsoup4, lxml, psutil",
        }

    Path(a.raw).write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(raw, Path(a.report))
    print(f"\n原始数据 -> {a.raw}\n对比表   -> {a.report}")
    return 0


def write_report(raw: dict, path: Path) -> None:
    keys = list(raw["schemes"].keys())
    head = "| 指标 | " + " | ".join(raw["schemes"][k]["label"] for k in keys) + " |"
    sep = "| --- |" + " --- |" * len(keys)
    rows = [
        ("端到端耗时（中位数，s）", [raw["schemes"][k]["median_sec"] for k in keys]),
        ("单页耗时（s）", [raw["schemes"][k]["sec_per_page"] for k in keys]),
        ("峰值内存（MB，进程树）", [raw["schemes"][k]["median_peak_mb"] for k in keys]),
        ("传输量（KB）", [round((raw["schemes"][k]["bytes_total"] or 0) / 1024, 1) for k in keys]),
        ("抓取条数", [raw["schemes"][k]["rows"] for k in keys]),
        ("有效代码行", [raw["schemes"][k]["loc"] for k in keys]),
        ("稳定性（成功轮数）", [raw["schemes"][k]["stability"] for k in keys]),
        ("依赖", [raw["schemes"][k]["deps"] for k in keys]),
    ]
    body = "\n".join("| " + name + " | " + " | ".join(str(v) for v in vals) + " |"
                     for name, vals in rows)
    md = f"""# 双方案对比（自动生成）

- 生成时间：{raw['generated_at']}
- 目标页：`{raw['page_url']}`
- 接口：`{raw['api'] or '未提供（方案 A 走嗅探）'}`
- 页数：{raw['pages']} ｜ 每方案重复：{raw['rounds']} 轮取中位数

{head}
{sep}
{body}

## 怎么读这张表

1. **耗时对比**只看中位数，不看单轮极值；首轮含冷启动，波动最大。
2. **峰值内存**是进程树合计（含 chromium 子进程），方案 B 通常高一个数量级。
3. **传输量**方案 B 已开启资源拦截（图片/字体/样式被 abort），否则差距更大。
4. **条数**必须一致，不一致先查懒加载是否漏滚、接口是否漏末页。
5. 结论请写成条件句（见需求文档 02 第 8.2 节），不要写"各有优劣"。
"""
    path.write_text(md, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
