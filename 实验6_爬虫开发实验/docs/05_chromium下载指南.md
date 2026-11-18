# 自己下载 Chromium（Playwright 浏览器内核）

## 0. 先弄清楚"要下的是哪一个"

Playwright 不是随便下个 Chrome 就能用，它按**版本号**认内核。查当前环境需要什么：

```bash
.venv/Scripts/python.exe -c "import json,pathlib,sys; \
p=pathlib.Path(sys.prefix)/'Lib/site-packages/playwright/driver/package/browsers.json'; \
[print(b['name'], b.get('revision'), b.get('browserVersion')) for b in json.load(open(p))['browsers'] if 'chromium' in b['name']]"
```

本机输出：

```
chromium 1255 159.0.8154.6
chromium-headless-shell 1255 159.0.8154.6
```

意思是：需要 **revision 1255**，对应的真实浏览器是 **Chrome for Testing 159.0.8154.6**。
所以 `chromium-1255` 和 `chrome-for-testing 159.0.8154.6` 是同一个东西，下载哪个都能用。

---

## 1. 路线一：官方源（网络通时最省事）

```bash
.venv/Scripts/python.exe -m playwright install chromium
```

下载失败通常是出站被挡。先确认是不是代理问题：

```bash
# 有可用代理就显式喂给它
HTTPS_PROXY=http://127.0.0.1:7890 HTTP_PROXY=http://127.0.0.1:7890 \
  .venv/Scripts/python.exe -m playwright install chromium
```

官方下载源的域名是 `cdn.playwright.dev`（部分版本回落 `playwright.azureedge.net`）与 `storage.googleapis.com`（Chrome for Testing）。这两个在国内都不稳，报 `Download failure, code=1` 就是这一步断了。

> 不要指望 `PLAYWRIGHT_DOWNLOAD_HOST` 指向 npmmirror：它只镜像 playwright 自己的 `/builds/...` 路径，而新版 playwright 已经改从 CfT 拿包，那条路我实测是 **404**。

---

## 2. 路线二：从镜像下 CfT 包（推荐，实测可用）

淘宝 npmmirror 完整镜像了 Chrome for Testing，地址规律：

```
https://cdn.npmmirror.com/binaries/chrome-for-testing/<版本号>/<平台>/chrome-<平台>.zip
```

Windows 64 位：

```
https://cdn.npmmirror.com/binaries/chrome-for-testing/159.0.8154.6/win64/chrome-win64.zip
```

文件大小 **217,364,368 字节**，下完先对一下，不够就是断了。

### Git Bash

```bash
mkdir -p 爬虫实验/.browsers && cd 爬虫实验/.browsers
curl -L -C - --retry 3 -o chrome-win64.zip \
  "https://cdn.npmmirror.com/binaries/chrome-for-testing/159.0.8154.6/win64/chrome-win64.zip"
unzip -q chrome-win64.zip
./chrome-win64/chrome.exe --version
```

`-C -` 是断点续传：断了重跑同一条命令接着下，不用从头再来。

### PowerShell

```powershell
$u = "https://cdn.npmmirror.com/binaries/chrome-for-testing/159.0.8154.6/win64/chrome-win64.zip"
Invoke-WebRequest $u -OutFile chrome-win64.zip
Expand-Archive chrome-win64.zip -DestinationPath .
& ".\chrome-win64\chrome.exe" --version
```

### 其他平台

| 平台 | 路径片段 | 包名 |
| --- | --- | --- |
| Windows x64 | `/win64/` | `chrome-win64.zip` |
| Windows x86 | `/win32/` | `chrome-win32.zip` |
| macOS Intel | `/mac-x64/` | `chrome-mac-x64.zip` |
| macOS ARM | `/mac-arm64/` | `chrome-mac-arm64.zip` |
| Linux x64 | `/linux64/` | `chrome-linux64.zip` |

---

## 3. 路线三：一个字节都不下

本机已有 Chrome 或 Edge 时，Playwright 可以直接驱动它，只是版本不完全可控：

```bash
python browser_crawler.py <URL> --channel chrome
python browser_crawler.py <URL> --channel msedge
```

做实验、交作业足够用；要严格复现某个内核行为时才需要自带 chromium。

---

## 4. 下完之后怎么让脚本用上

### 4.1 推荐：`--exe` 直接指路径

```bash
python browser_crawler.py "http://127.0.0.1:8899/spa_live.html" \
  --exe "爬虫实验/.browsers/chrome-win64/chrome.exe"
```

也可以设环境变量，避免每次敲长路径：

```bash
export BROWSER_EXE="$PWD/爬虫实验/.browsers/chrome-win64/chrome.exe"
python browser_crawler.py <URL>
```

脚本里对应的就是这一句：

```python
browser = pw.chromium.launch(headless=True, executable_path=exe)
```

`executable_path` 绕开了 Playwright 的版本校验，只要那个 exe 是 Chromium 内核就能跑。

### 4.2 不推荐：往 ms-playwright 目录里塞

网上教程会让你解压到 `%LOCALAPPDATA%\ms-playwright\chromium-1255\` 并建一个 `INSTALLATION_COMPLETE` 标记文件。能做，但目录结构（`chrome-win` 还是 `chrome-win64`）随版本变，塞错了 Playwright 只会报 `Executable doesn't exist`，排查成本比 `--exe` 高。除非需要 `playwright install --list` 认账，否则别走这条。

---

## 5. 验证清单

```bash
# 1) 文件在不在、多大
ls -l 爬虫实验/.browsers/chrome-win64.zip        # 应该 217364368 左右

# 2) exe 能不能起来
爬虫实验/.browsers/chrome-win64/chrome.exe --version

# 3) Playwright 能不能驱动它
python -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(headless=True, executable_path='爬虫实验/.browsers/chrome-win64/chrome.exe')
    pg = b.new_page(); pg.set_content('<h1>ok</h1>')
    print('version =', b.version); print('text =', pg.inner_text('h1'))
    b.close()
"
```

三行都过，说明内核可用，`--exe` 可以放心用。

---

## 6. 报错对照

| 报错 | 含义 | 处理 |
| --- | --- | --- |
| `Download failure, code=1` | 出站被挡 | 走路线二下 zip |
| `Executable doesn't exist at ...ms-playwright\chromium-1255\...` | 没装内核 | `--channel chrome` 或 `--exe` |
| `net::ERR_CONNECTION_RESET`（下载时） | 镜像/源被断 | `curl -C -` 续传重试 |
| `zipfile.BadZipFile` | 包没下完 | 核对字节数，重下 |
| `Target page, context or browser has been closed` | exe 路径写错或权限不足 | 用绝对路径，确认 exe 能单独启动 |
| `Executable path is not absolute` | 传了相对路径 | 换绝对路径 |

---

## 7. 实测记录（2026-11-18 本机）

按路线二完整走了一遍，全程无代理配置、无梯子：

| 步骤 | 结果 |
| --- | --- |
| 探测文件 | `HTTP 200`，`Content-Length: 217364368` |
| 下载 | 3 分 21 秒，平均 1.03 MB/s，`downloaded 217364368 bytes` |
| 解压 | `unzip chrome-win64.zip` → `chrome-win64/chrome.exe` |
| 版本 | `Google Chrome for Testing 159.0.8154.6`（与 browsers.json 要求完全一致） |
| 跑脚本 | `browser_crawler.py --exe ...` → 5 条，6.0s，峰值 633MB |

落盘位置：`爬虫实验/.browsers/chrome-win64/`（207MB 的 zip 可删）。

---

## 8. 占多大、怎么清

| 目录 | 大小 | 说明 |
| --- | --- | --- |
| `.browsers/chrome-win64.zip` | 217 MB | 装完即可删 |
| `.browsers/chrome-win64/` | 约 320 MB | 解压后的内核 |
| `%LOCALAPPDATA%\ms-playwright\` | 每个内核 150–320 MB | 官方安装位置，可整体删 |

删掉不影响方案 A（`api_crawler.py` 纯 requests，不需要浏览器）。
