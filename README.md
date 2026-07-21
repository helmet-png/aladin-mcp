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

# Several charts in one resident Aladin — roughly 3x faster than one call each
python aladin_cli.py batch M31 M51 M13 --fov 0.5 --grid

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

## Performance

Where the time goes on a cold `aladin_chart` call, measured on Windows/ARM64:

| Stage | Cost |
|---|---|
| JVM startup | 0.2 s |
| Aladin class loading and init | ~6 s |
| Resolving the survey and fetching tiles | the rest, network-bound |

Three things follow from that, all of which this repo does:

**Keep Aladin resident.** The MCP server holds one Aladin process for its
lifetime, and the CLI's `batch` command does the same. A warm session skips
startup *and* keeps the resolved HiPS registry and tile cache in memory:
measured 15.7 s for the first chart, then 5.3 s and 5.1 s.

**Don't clear the plane stack.** `rm all` between charts throws away exactly the
cached tiles that make a warm session fast — it roughly triples render time.
Instead the catalog planes get fixed names and only those are removed, leaving
image planes (and their caches) in place.

**Use a native JVM and a class-sharing archive.** Aladin ships an x64 JRE, which
runs emulated on ARM64 machines (Apple Silicon under Rosetta, Snapdragon X on
Windows). `Aladin-Fast.bat` launches the same jar on a native JVM, raises the
heap limit, and builds an AppCDS archive on first run (~6.1 s → ~4.6 s startup;
the gain is limited because Aladin.jar is signed, so only JDK classes can be
archived).

## Gotchas

- **An Aladin script whose last line has no trailing newline hangs forever** —
  the process never exits and must be killed. `run_aladin_script()` appends one.
- **Overlays and the grid persist across charts in a resident session.** Every
  chart script therefore removes the named overlay planes and sets `grid on|off`
  explicitly rather than assuming a clean slate — otherwise a chart that asked
  for no catalog still shows the previous chart's markers.
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

# 一個常駐程序連續出多張圖（約快 3 倍）
python aladin_cli.py batch M31 M51 M13 --fov 0.5 --grid

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

## 效能

冷啟動一次 `aladin_chart` 的時間分佈（Windows/ARM64 實測）：

| 階段 | 耗時 |
|---|---|
| JVM 啟動 | 0.2 秒 |
| Aladin 類別載入與初始化 | 約 6 秒 |
| 解析巡天、下載影像磚 | 其餘，取決於網路 |

由此得到三個對策，本專案都做了：

**讓 Aladin 常駐。** MCP 伺服器在生命週期內只開一個 Aladin，CLI 的 `batch` 指令同理。
熱的 session 不只省下啟動時間，解析好的 HiPS 註冊表與影像磚也還在記憶體裡：
實測第一張 15.7 秒，之後 5.3 秒、5.1 秒。

**不要清空圖層堆疊。** 在兩張圖之間下 `rm all`，丟掉的正是讓熱 session 變快的那份快取，
算圖時間會變成約三倍。改成只給目錄圖層固定名稱、只刪那些，影像圖層（與其快取）保留。

**用原生 JVM 加類別共享存檔。** Aladin 自帶 x64 JRE，在 ARM64 機器上（Apple Silicon
走 Rosetta、Windows 的 Snapdragon X）是模擬執行。`Aladin-Fast.bat` 改用原生 JVM 啟動、
提高記憶體上限，並在首次執行時建立 AppCDS 存檔（啟動 6.1 秒 → 4.6 秒；因為 Aladin.jar
有簽章、自身類別無法進存檔，增益有限）。

## 陷阱

- **腳本最後一行沒有換行，Aladin 會無限卡死**，程序不退出、得強制終止。
  `run_aladin_script()` 已自動補上。
- **常駐 session 裡，疊加層與網格會殘留到下一張圖。** 所以每段腳本都會先刪掉具名的
  疊加層、並明確設定 `grid on|off`，不能假設是乾淨狀態——否則「沒要求目錄」的圖上
  會出現前一張的標記。
- 腳本裡 `save` 的路徑要用絕對路徑加正斜線。
- Aladin 的 log 含非 ASCII 字元，舊版 Windows 主控台編碼會炸；CLI 已強制 UTF-8。

## 致謝

這個工具只是一層薄包裝。真正的巡天資料、Aladin 軟體與 hips2fits 服務都是
[史特拉斯堡大學 CDS](https://cds.unistra.fr/) 的成果。若用它產出的結果要發表，
請引用 Aladin 與你使用的巡天。

MIT 授權。
