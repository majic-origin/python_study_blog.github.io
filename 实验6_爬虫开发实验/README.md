# 爬虫实验（Vibe Coding · requests + BeautifulSoup + Playwright）

一个文件夹装完整个实验：需求文档、可运行代码、示例数据、实测对比。

## 30 秒上手

```bash
cd 爬虫实验
python run.py 检查          # 看环境齐不齐
python run.py 演示          # 本地样例跑全套，不联网，30 秒出结果
```

演示跑完，`示例/results/` 里会多出 5 个文件：3 份 CSV + 1 份对比表 + 1 份原始数据。

Windows 想点鼠标的，双击 **`一键运行.bat`**，菜单选 1 或 2 即可。

## 只有一个入口

所有功能都从 `run.py` 进，不用记四个脚本名：

| 命令 | 干什么 | 产出 |
| --- | --- | --- |
| `python run.py 检查` | 自检依赖与浏览器内核 | 终端报告 |
| `python run.py 演示 [轮数]` | 本地样例全套流程 | `示例/results/*` |
| `python run.py 基础 <URL>` | 静态列表页抓取 | `result.csv` |
| `python run.py 接口 <URL>` | 自动嗅探 XHR 接口后抓取（方案 A） | `result_api.csv` |
| `python run.py 渲染 <URL>` | 浏览器渲染后抓取（方案 B） | `result_browser.csv` |
| `python run.py 对比 --page-url <页面> --api <接口>` | 双方案测量 | `compare.md`、`metrics_raw.json` |
| `python run.py 文档` | 列出文档路径 | 终端列表 |

英文命令等价：`doctor / demo / basic / api / render / compare / docs`。

### 常用参数

```bash
python run.py 基础 https://example.com/news -o news.csv --pages 3 --delay 2.5
python run.py 基础 https://example.com/news --selector "div.news-item"
python run.py 渲染 https://example.com/news --pages 3 --channel chrome
python run.py 对比 --page-url https://example.com/news --api "https://example.com/api/list?page=1" --rounds 3
```

## 目录结构

```
爬虫实验/
├── run.py                 ← 唯一入口，先看这个
├── 一键运行.bat           ← Windows 双击菜单
├── README.md              ← 本文件
├── src/                   ← 实现代码（一般不用直接跑）
│   ├── crawler_core.py       请求 / 解析 / 写 CSV 的公共库
│   ├── api_crawler.py        方案 A：接口逆向
│   ├── browser_crawler.py    方案 B：Playwright 渲染
│   └── metrics.py            双方案测量与对比表
├── docs/                  ← 5 份文档
│   ├── 01_基础任务_静态网页爬虫需求文档.md
│   ├── 02_进阶挑战_动态渲染爬虫需求文档.md
│   ├── 03_运行说明.md
│   ├── 04_进阶方案说明.md
│   └── 05_chromium下载指南.md
├── 示例/                  ← 可离线运行的样例页与结果
│   ├── list.html             静态列表页（12 条）
│   ├── spa_live.html         JS 渲染页（5 条）
│   ├── spa.html              内联 JSON 空壳页（4 条）
│   ├── api/list.json         模拟接口返回
│   └── results/              跑出来的 CSV 与对比表
└── .browsers/             ← 手动下载的 Chrome 内核（约 660MB，可不入库）
```

## 输出文件

| 文件 | 内容 |
| --- | --- |
| `result.csv` / `result_basic.csv` | 基础抓取结果 |
| `result_api.csv` | 方案 A 结果 |
| `result_browser.csv` | 方案 B 结果 |
| `compare.md` | 双方案对比表（耗时/内存/传输量/条数） |
| `metrics_raw.json` | 每轮原始测量值 |
| `metrics_api.json` / `metrics_browser.json` | 单方案指标快照 |

CSV 一律 `utf-8-sig`、列序 `title,time,author,url`，Excel 双击直接开，不乱码。

## 出问题先看这里

| 现象 | 处理 |
| --- | --- |
| `python` 找不到 | 用 `..\.venv\Scripts\python.exe run.py ...` |
| 缺少 requests / bs4 | `uv pip install --python ..\.venv\Scripts\python.exe requests beautifulsoup4 lxml` |
| 浏览器方案报 `Executable doesn't exist` | `python run.py 渲染 <URL> --channel chrome`，或看 `docs/05_chromium下载指南.md` |
| 抓到 0 条 | 加 `--selector "div.xxx"` 指定条目容器；或页面是 JS 渲染，改用 `渲染` 命令 |
| 本地样例访问被代理拦成 502 | 加 `NO_PROXY=127.0.0.1` 环境变量 |

## 实测结论（2026-11-18，5 条数据 3 轮中位数）

| 指标 | A 接口逆向 | B 浏览器渲染 |
| --- | --- | --- |
| 端到端耗时 | 0.85 s | 6.87 s |
| 峰值内存 | 51.3 MB | 638.5 MB |
| 传输量 | 0.9 KB | 1.8 KB |

**能拿到 JSON 就别开浏览器。** 8 倍耗时、12 倍内存就是这句话的价格。

## 发布到 GitHub

仓库：`https://github.com/majic-origin/python_study_blog.github.io.git`
本目录对应该仓库里的 `实验6_爬虫开发实验/`。

```bash
git clone https://github.com/majic-origin/python_study_blog.github.io.git blogrepo
cd blogrepo
# 把本地改动同步进去（排除体积大的内核与运行产物）
rsync -a --delete \
  --exclude '.browsers' --exclude '__pycache__' --exclude '_metrics' \
  "../ai实验报告完成/爬虫实验/" "实验6_爬虫开发实验/"
git add -A && git commit -m "更新实验6" && git push
```

不想用 rsync 的话，直接把 `爬虫实验/` 整个复制覆盖 `blogrepo/实验6_爬虫开发实验/` 即可。

`.gitignore` 已经排除：`.browsers/`（660MB 内核）、`_metrics/`（日志）、`__pycache__/`，`示例/results/` 里的 CSV 与对比表则保留入库，方便别人直接看结果。

