#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run.py —— 爬虫实验的唯一入口。记住这一个文件就够了。

    python run.py 检查                    环境自检（依赖 / 浏览器内核）
    python run.py 演示                    一键跑通全套（本地样例，不联网）
    python run.py 基础 <URL>               静态列表页 → result.csv
    python run.py 接口 <URL>               从 JSON 接口抓（自动找接口）
    python run.py 渲染 <URL>               动态页面，用浏览器渲染
    python run.py 对比                     双方案测量出对比表
    python run.py 文档                     列出所有文档路径
    python run.py 菜单                     交互菜单（双击 一键运行.bat 等同此命令）

英文别名同样可用：doctor / demo / basic / api / render / compare / docs
"""
from __future__ import annotations

import functools
import http.server
import importlib
import os
import socketserver
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
SAMPLE = ROOT / "示例"
DOCS = ROOT / "docs"
CHROME = ROOT / ".browsers" / "chrome-win64" / "chrome.exe"

sys.path.insert(0, str(SRC))

# 本地回环不走系统代理；有自带内核就指给它
os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
if CHROME.exists():
    os.environ.setdefault("BROWSER_EXE", str(CHROME))

ALIAS = {
    "检查": "doctor", "自检": "doctor",
    "演示": "demo", "示例": "demo",
    "基础": "basic", "静态": "basic",
    "接口": "api", "嗅探": "api",
    "渲染": "render", "动态": "render", "浏览器": "render",
    "对比": "compare", "测量": "compare",
    "文档": "docs", "说明": "docs",
    "菜单": "menu", "交互": "menu",
}


def call(module: str, argv: list[str]) -> int:
    """把参数转交给 src 里的模块，等价于直接跑那个脚本。"""
    mod = importlib.import_module(module)
    sys.argv = [f"{module}.py", *argv]
    try:
        rc = mod.main()
        return int(rc or 0)
    except SystemExit as e:
        return int(e.code or 0)


# ------------------------------------------------------------------ 检查
def cmd_doctor() -> int:
    print("=" * 58)
    print(" 环境自检")
    print("=" * 58)
    print(f" Python      : {sys.version.split()[0]}")
    print(f" 项目目录    : {ROOT}")

    ok = {}
    for name, mod in [("requests", "requests"), ("beautifulsoup4", "bs4"),
                      ("lxml", "lxml"), ("playwright", "playwright"), ("psutil", "psutil")]:
        try:
            m = importlib.import_module(mod)
            ok[name] = getattr(m, "__version__", "已安装")
        except ImportError:
            ok[name] = None
    for name, ver in ok.items():
        print(f" {name:<12}: {ver if ver else '✗ 未安装'}")

    print("-" * 58)
    if CHROME.exists():
        print(f" 浏览器内核  : 自带 {CHROME}")
    else:
        print(" 浏览器内核  : 未发现 .browsers/chrome-win64/chrome.exe")
        print("               可用 --channel chrome 调本机 Chrome，或看 docs/05_chromium下载指南.md")

    can_static = bool(ok["requests"] and ok["beautifulsoup4"])
    can_browser = bool(ok["playwright"])
    print("-" * 58)
    print(f" 基础抓取(静态/接口): {'✓ 可用' if can_static else '✗ 缺依赖'}")
    print(f" 动态渲染          : {'✓ 可用' if can_browser else '✗ 缺 playwright'}")
    print("=" * 58)
    if can_static:
        print(" 下一步：python run.py 演示        （本地样例，30 秒跑完）")
    else:
        print(" 先装依赖：uv pip install --python ..\\.venv\\Scripts\\python.exe requests beautifulsoup4 lxml")
    return 0


# ------------------------------------------------------------------ 演示
def _serve(directory: Path, port: int):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    handler = functools.partial(Quiet, directory=str(directory))
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", port), handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def cmd_demo(rounds: int = 1) -> int:
    port = 8899
    srv = _serve(SAMPLE, port)
    time.sleep(0.5)
    base = f"http://127.0.0.1:{port}"
    out = SAMPLE / "results"
    out.mkdir(exist_ok=True)

    print("\n################################################################")
    print("# 第 1 步 / 4  静态列表页（requests + BeautifulSoup）")
    print("################################################################")
    call("crawler_core", [f"{base}/list.html", "-o", str(out / "result_basic.csv")])

    print("\n################################################################")
    print("# 第 2 步 / 4  JSON 接口（方案 A）")
    print("################################################################")
    call("api_crawler", [f"{base}/api/list.json?page=1", "-o", str(out / "result_api.csv"),
                         "--max-pages", "1", "--metrics", str(out / "metrics_api.json")])

    print("\n################################################################")
    print("# 第 3 步 / 4  动态页面渲染（方案 B）")
    print("################################################################")
    rc = call("browser_crawler", [f"{base}/spa_live.html", "-o", str(out / "result_browser.csv"),
                                  "--metrics", str(out / "metrics_browser.json")])
    if rc != 0:
        print("\n[!] 浏览器方案没跑通（多半是内核缺失），前两步不受影响。")

    print("\n################################################################")
    print("# 第 4 步 / 4  双方案对比")
    print("################################################################")
    call("metrics", ["--page-url", f"{base}/spa_live.html",
                     "--api", f"{base}/api/list.json?page=1",
                     "--pages", "1", "--rounds", str(rounds),
                     "--out-dir", str(out / "_metrics"),
                     "--raw", str(out / "metrics_raw.json"),
                     "--report", str(out / "compare.md")])

    srv.shutdown()
    print("\n" + "=" * 58)
    print(f" 演示结束，结果都在：{out}")
    for f in sorted(out.glob("*")):
        if f.is_file():
            print(f"   - {f.name}")
    print("=" * 58)
    return 0


# ------------------------------------------------------------------ 文档
def cmd_docs() -> int:
    print("文档清单（用编辑器或浏览器打开）:\n")
    for i, f in enumerate(sorted(DOCS.glob("*.md")), 1):
        title = f.stem
        print(f"  {i}. {title}")
        print(f"     {f}")
    print(f"\n 入口脚本: {ROOT / 'run.py'}")
    print(f" 源码目录: {SRC}")
    print(f" 样例目录: {SAMPLE}")
    return 0


# ------------------------------------------------------------------ 交互菜单
MENU = """
============================================================
  爬虫实验 · 菜单          （Ctrl+C 或 0 退出）
============================================================
   1  环境检查（依赖 / 浏览器内核）
   2  一键演示（本地样例，不联网，约 30 秒）
   3  抓静态列表页          -> result.csv
   4  抓接口 / 动态页面      （自动嗅探，方案 A）
   5  渲染动态页面          （浏览器，方案 B）
   6  双方案对比            -> compare.md
   7  查看文档清单
   0  退出
============================================================
"""


def _ask(prompt: str):
    """读一行输入；遇到 EOF（管道 / 双击关窗口）返回 None。"""
    try:
        return input(prompt).strip()
    except EOFError:
        return None


def _pause():
    try:
        input("\n按回车回到菜单...")
        return True
    except EOFError:
        return False


def cmd_menu() -> int:
    while True:
        print(MENU)
        choice = _ask("请输入序号后回车: ")
        if choice is None or choice in ("0", "q", "quit", "exit"):
            print("已退出。")
            return 0

        try:
            if choice == "1":
                cmd_doctor()
            elif choice == "2":
                cmd_demo(1)
            elif choice == "3":
                url = _ask("列表页 URL（直接回车跳过）: ")
                if url:
                    call("crawler_core", [url, "-o", "result.csv"])
                    print("\n输出文件: result.csv")
            elif choice == "4":
                url = _ask("页面 URL（直接回车跳过）: ")
                if url:
                    call("api_crawler", ["--sniff", url, "-o", "result_api.csv"])
                    print("\n输出文件: result_api.csv")
            elif choice == "5":
                url = _ask("页面 URL（直接回车跳过）: ")
                if url:
                    call("browser_crawler", [url, "-o", "result_browser.csv"])
                    print("\n输出文件: result_browser.csv")
            elif choice == "6":
                page = _ask("页面 URL: ")
                api = _ask("接口 URL（回车则由脚本自动嗅探）: ")
                if page:
                    argv = ["--page-url", page, "--rounds", "3"]
                    if api:
                        argv += ["--api", api]
                    call("metrics", argv)
                    print("\n输出文件: compare.md / metrics_raw.json")
            elif choice == "7":
                cmd_docs()
            else:
                print("没有这个序号，输入 1–7 或 0。")
        except KeyboardInterrupt:
            print("\n已中断。")
            return 0
        except Exception as e:                      # 单个任务失败不应炸掉菜单
            print(f"\n[!] 这一步出错: {type(e).__name__}: {e}")

        if not _pause():
            return 0


# ------------------------------------------------------------------ 主入口
HELP = __doc__


def main() -> int:
    # 输出重定向到文件时（编码非 UTF-8）避免个别符号触发 UnicodeEncodeError
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass

    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(HELP)
        return 0

    cmd = ALIAS.get(sys.argv[1], sys.argv[1])
    rest = sys.argv[2:]

    if cmd == "doctor":
        return cmd_doctor()
    if cmd == "demo":
        rounds = 1
        if rest and rest[0].isdigit():
            rounds = int(rest[0])
        return cmd_demo(rounds)
    if cmd == "docs":
        return cmd_docs()
    if cmd == "menu":
        return cmd_menu()
    if cmd == "basic":
        if not rest:
            print("用法: python run.py 基础 <URL> [-o 输出.csv] [--pages N]")
            return 2
        return call("crawler_core", rest)
    if cmd == "api":
        if not rest:
            print("用法: python run.py 接口 <页面或接口URL> [--sniff 显式嗅探]")
            return 2
        # 第一次给的通常是页面地址，自动走嗅探；给了 --api 则直连
        if "--api" in rest or "--sniff" in rest:
            return call("api_crawler", rest)
        return call("api_crawler", ["--sniff", rest[0], *rest[1:]])
    if cmd == "render":
        if not rest:
            print("用法: python run.py 渲染 <URL> [--pages N] [--selector CSS]")
            return 2
        return call("browser_crawler", rest)
    if cmd == "compare":
        if not rest:
            print("用法: python run.py 对比 --page-url <页面> --api <接口> [--rounds 3]")
            return 2
        return call("metrics", rest)

    print(f"未知命令: {sys.argv[1]}\n")
    print(HELP)
    return 2


if __name__ == "__main__":
    sys.exit(main())
