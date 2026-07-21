# Aladin Sky Charts — CLI + MCP

Generate astronomical sky charts and research images from the command line, or
let an AI assistant do it for you. Built on [CDS Aladin](https://aladin.cds.unistra.fr/)
and the [hips2fits](https://alasky.cds.unistra.fr/hips-image-services/hips2fits) service.

> 中文說明請見 [下方中文版](#中文說明)。

## Two engines

| Engine | Speed | Needs Aladin Desktop | What it does |
|---|---|---|---|
| **hips2fits** | 1–3 s | No | Sky images from any HiPS survey, any position, any field of view. Can output FITS. |
| **Aladin headless** | 20–40 s | Yes | Catalog overlays (Simbad, VizieR), coordinate grids, contours, RGB composition |

Use the fast engine for illustrations and quick looks; use Aladin when you need
catalog data drawn on top.

## Install

Requires Python 3.8+ (no third-party packages). For the second engine you also
need [Aladin Desktop](https://aladin.cds.unistra.fr/java/nph-aladin.pl?frame=downloading)
and a Java runtime.

```bash
git clone https://github.com/helmet-png/aladin-mcp.git
cd aladin-mcp
python aladin_cli.py chart M31 --fov 1.5
```

`Aladin.jar` is found automatically in the usual install locations. Override with
the `ALADIN_JAR` environment variable if you keep it elsewhere; `JAVA_BIN` selects
a specific JVM and `ALADIN_OUT` changes the output directory.

## CLI

```bash
# Fast charts
python aladin_cli.py chart M31 --fov 1.5
python aladin_cli.py chart "10.68,41.27" --survey 2mass --fov 0.5   # RA,Dec in degrees
python aladin_cli.py chart M42 --format fits                        # raw data for analysis
python aladin_cli.py chart "0,0" --fov 360 --projection AIT --survey mellinger

# With catalog overlays and a coordinate grid
python aladin_cli.py aladin M45 --fov 1.5 --catalog simbad --grid
python aladin_cli.py aladin M13 --catalog I/355/gaiadr3             # Gaia DR3

# Raw Aladin script passthrough — contours, RGB, crossmatch, anything
python aladin_cli.py script "get hips(CDS/P/DSS2/red) M1 20arcmin; sync; contour 8; save -png 800x600 /tmp/m1.png"

python aladin_cli.py surveys    # list survey aliases
```

Images land in `output/` unless you pass `--out`.

### Survey aliases

`dss` `dss-red` `dss-blue` `2mass` `sdss` `decals` `panstarrs` `galex` `wise`
`iras` `halpha` `xmm` `fermi` `planck` `mellinger` `gaia-density`

Any full HiPS id also works, e.g. `CDS/P/DSS2/color`. Browse the full list at the
[HiPS registry](https://aladin.cds.unistra.fr/hips/list).

## MCP server

`mcp_server.py` exposes the same functionality over the
[Model Context Protocol](https://modelcontextprotocol.io) as three tools:
`star_chart`, `aladin_chart`, and `aladin_script`. Charts are returned inline to
the assistant. It is a dependency-free stdio server — plain Python, no SDK.

```bash
claude mcp add aladin -- python /path/to/mcp_server.py
```

Or in `claude_desktop_config.json`:

```json
{ "mcpServers": { "aladin": { "command": "python", "args": ["/path/to/mcp_server.py"] } } }
```

Note that browser-based clients cannot reach a local MCP server — they accept
remote URLs only. Desktop clients work fine.

## Running Aladin on a native JVM

Aladin Desktop ships with an x64 JRE. On ARM64 machines (Apple Silicon under
Rosetta, Snapdragon X on Windows) that JRE runs emulated. `Aladin-Fast.bat`
launches the same jar on whatever native JVM is on your PATH and raises the heap
limit. Measured ~15% faster on batch rendering, with a larger difference on
interactive panning and zooming, which is CPU-bound.

## Gotchas

- **An Aladin script whose last line has no trailing newline hangs forever** —
  the process never exits and must be killed. `run_aladin_script()` appends one.
- `save` paths inside Aladin scripts must be absolute, with forward slashes.
- Aladin's log output contains non-ASCII characters that crash legacy Windows
  console codepages; the CLI forces UTF-8.

## Credits

This tool is a thin wrapper. The actual sky surveys, the Aladin software and the
hips2fits service are the work of [CDS, Université de Strasbourg](https://cds.unistra.fr/).
If you publish results made with it, cite Aladin
([2000A&AS..143...33B](https://ui.adsabs.harvard.edu/abs/2000A%26AS..143...33B),
[2014ASPC..485..277B](https://ui.adsabs.harvard.edu/abs/2014ASPC..485..277B))
and the surveys you used.

MIT licensed.

---

# 中文說明

用命令列產生天文星圖與研究影像，也可以讓 AI 助理直接幫你產。建立在
[CDS Aladin](https://aladin.cds.unistra.fr/) 與
[hips2fits](https://alasky.cds.unistra.fr/hips-image-services/hips2fits) 服務之上。

## 兩個引擎

| 引擎 | 速度 | 需要 Aladin | 用途 |
|---|---|---|---|
| **hips2fits** | 1–3 秒 | 否 | 任意巡天／座標／視野的星圖，可出 FITS |
| **Aladin 無介面** | 20–40 秒 | 是 | 疊目錄（Simbad、VizieR）、座標網格、等高線、RGB 合成 |

出示意圖用快的；需要把目錄資料疊上去時才用 Aladin。

## 安裝

需要 Python 3.8+（無第三方套件）。第二個引擎另需
[Aladin Desktop](https://aladin.cds.unistra.fr/java/nph-aladin.pl?frame=downloading)
與 Java。

`Aladin.jar` 會自動在常見安裝路徑尋找。裝在別處的話用環境變數 `ALADIN_JAR` 指定；
`JAVA_BIN` 指定 JVM，`ALADIN_OUT` 改輸出資料夾。

## 用法

```bash
# 快速星圖
python aladin_cli.py chart M31 --fov 1.5
python aladin_cli.py chart "10.68,41.27" --survey 2mass --fov 0.5   # 度為單位的赤經,赤緯
python aladin_cli.py chart M42 --format fits                        # 給後續分析的原始資料
python aladin_cli.py chart "0,0" --fov 360 --projection AIT --survey mellinger  # 全天圖

# 疊目錄 + 網格
python aladin_cli.py aladin M45 --fov 1.5 --catalog simbad --grid
python aladin_cli.py aladin M13 --catalog I/355/gaiadr3             # 疊 Gaia DR3

# 原生腳本直通（等高線、RGB、crossmatch⋯⋯）
python aladin_cli.py script "get hips(CDS/P/DSS2/red) M1 20arcmin; sync; contour 8; save -png 800x600 /tmp/m1.png"

python aladin_cli.py surveys    # 列出巡天代號
```

輸出預設在 `output/`，可用 `--out` 指定。

## MCP 伺服器

`mcp_server.py` 把同樣的功能透過 [MCP](https://modelcontextprotocol.io) 提供三個工具：
`star_chart`、`aladin_chart`、`aladin_script`，圖片會直接回傳給助理。零依賴的 stdio 伺服器，
純 Python、不需要 SDK。

```bash
claude mcp add aladin -- python /path/to/mcp_server.py
```

注意瀏覽器版的客戶端接不到本機 MCP（只接受遠端 URL），桌面版才可以。

## 讓 Aladin 跑更快

Aladin 自帶 x64 的 JRE。在 ARM64 機器上（Apple Silicon 走 Rosetta、Windows 的
Snapdragon X）那個 JRE 是模擬執行的。`Aladin-Fast.bat` 改用 PATH 上的原生 JVM
啟動同一個 jar，並提高記憶體上限。實測批次算圖快約 15%，互動平移縮放（純 CPU）差距更大。

## 陷阱

- **腳本最後一行沒有換行，Aladin 會無限卡死**，程序不退出、得強制終止。
  `run_aladin_script()` 已自動補上。
- 腳本裡 `save` 的路徑要用絕對路徑加正斜線。
- Aladin 的 log 含非 ASCII 字元，舊版 Windows 主控台編碼會炸；CLI 已強制 UTF-8。

## 致謝

這個工具只是一層薄包裝。真正的巡天資料、Aladin 軟體與 hips2fits 服務都是
[史特拉斯堡大學 CDS](https://cds.unistra.fr/) 的成果。若用它產出的結果要發表，
請引用 Aladin 與你使用的巡天。

MIT 授權。
