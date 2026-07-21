#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aladin star-chart CLI.

Two engines:
  chart   -> hips2fits HTTP API (fast, no Aladin needed)
  aladin  -> Aladin Desktop headless script mode (catalogs, grid, contours...)
  script  -> raw Aladin script passthrough
  surveys -> list common survey ids

Examples:
  py aladin_cli.py chart M31 --fov 1.5
  py aladin_cli.py chart "10.68,41.27" --survey 2mass --format fits
  py aladin_cli.py aladin M45 --fov 2 --catalog simbad --grid
  py aladin_cli.py script "get hips(CDS/P/DSS2/color) M1 20arcmin; sync; save -png 800x600 m1.png"
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HIPS2FITS = "https://alasky.cds.unistra.fr/hips-image-services/hips2fits"
OUT_DIR = Path(os.environ.get("ALADIN_OUT", Path(__file__).resolve().parent / "output"))

# Where Aladin Desktop keeps its jar, per platform. ALADIN_JAR overrides.
_JAR_CANDIDATES = [
    r"C:\Program Files\Aladin\Aladin.jar",
    r"C:\Program Files (x86)\Aladin\Aladin.jar",
    "/Applications/Aladin.app/Contents/Resources/Aladin.jar",
    "/usr/share/aladin/Aladin.jar",
    "/opt/Aladin/Aladin.jar",
]


def find_aladin_jar():
    """Locate Aladin.jar, or raise with an actionable message."""
    env = os.environ.get("ALADIN_JAR")
    if env:
        if Path(env).is_file():
            return env
        raise FileNotFoundError(f"ALADIN_JAR points at a missing file: {env}")
    for c in _JAR_CANDIDATES + [str(Path(__file__).resolve().parent / "Aladin.jar")]:
        if Path(c).is_file():
            return c
    raise FileNotFoundError(
        "Aladin.jar not found. Install Aladin Desktop from "
        "https://aladin.cds.unistra.fr/java/nph-aladin.pl?frame=downloading "
        "or set the ALADIN_JAR environment variable to its path.\n"
        "(The 'chart' command works without Aladin — it only needs the network.)"
    )

# short alias -> HiPS id (full ids also accepted everywhere)
SURVEYS = {
    "dss": "CDS/P/DSS2/color",
    "dss-red": "CDS/P/DSS2/red",
    "dss-blue": "CDS/P/DSS2/blue",
    "2mass": "CDS/P/2MASS/color",
    "sdss": "CDS/P/SDSS9/color",
    "decals": "CDS/P/DECaLS/DR5/color",
    "panstarrs": "CDS/P/PanSTARRS/DR1/color-z-zg-g",
    "galex": "CDS/P/GALEXGR6/AIS/color",
    "wise": "CDS/P/allWISE/color",
    "iras": "CDS/P/IRIS/color",
    "halpha": "CDS/P/VTSS/Ha",
    "xmm": "xcatdb/P/XMM/PN/color",
    "fermi": "CDS/P/Fermi/color",
    "planck": "CDS/P/PLANCK/R2/HFI/color",
    "mellinger": "CDS/P/Mellinger/color",
    "gaia-density": "CDS/P/DM/flux-color-Rp-G-Bp/I/355/gaiadr3",
}


def resolve_survey(s):
    return SURVEYS.get(s.lower(), s)


def parse_target(target):
    """Return ('coords', ra, dec) or ('name', target)."""
    m = re.fullmatch(r"\s*([+-]?\d+(?:\.\d+)?)\s*[, ]\s*([+-]?\d+(?:\.\d+)?)\s*", target)
    if m:
        return ("coords", float(m.group(1)), float(m.group(2)))
    return ("name", target)


def default_out(target, fmt):
    OUT_DIR.mkdir(exist_ok=True)
    stem = re.sub(r"[^\w.+-]+", "_", target).strip("_") or "chart"
    return OUT_DIR / f"{stem}_{time.strftime('%H%M%S')}.{fmt}"


def make_chart(target, fov=1.0, survey="dss", width=1200, height=900,
               projection="TAN", fmt="png", out=None):
    """Fast engine: hips2fits. Returns output Path."""
    params = {
        "hips": resolve_survey(survey),
        "fov": fov, "width": width, "height": height,
        "projection": projection, "format": fmt,
    }
    t = parse_target(target)
    if t[0] == "coords":
        params["ra"], params["dec"] = t[1], t[2]
    else:
        params["object"] = t[1]
    url = HIPS2FITS + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (aladin-cli)"})
    # The CDS service occasionally resets a connection mid-transfer; retry a few times.
    for attempt in range(3):
        try:
            data = urllib.request.urlopen(req, timeout=120).read()
            break
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:300]
            raise RuntimeError(f"hips2fits returned HTTP {e.code}: {body}") from None
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            if attempt == 2:
                raise RuntimeError(f"hips2fits unreachable after 3 tries: {e}") from None
            time.sleep(2 * (attempt + 1))
    out = Path(out) if out else default_out(target, fmt)
    out.write_bytes(data)
    return out


def run_aladin_script(script, timeout=300):
    """Full engine: Aladin Desktop headless. Returns (returncode, output_text)."""
    script = script.rstrip() + "\n"  # Aladin only executes a line after its newline
    if not script.rstrip().endswith("quit"):
        script += "quit\n"
    java = os.environ.get("JAVA_BIN") or shutil.which("java")
    if not java:
        raise FileNotFoundError("java not found on PATH; set JAVA_BIN to a java executable.")
    try:
        p = subprocess.run(
            [java, "-jar", find_aladin_jar(), "-nogui", "-script"],
            input=script.encode("utf-8"),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise TimeoutError(
            f"Aladin did not finish within {timeout}s and was killed. A script whose "
            "last line lacks a trailing newline makes Aladin hang forever."
        )
    return p.returncode, p.stdout.decode("utf-8", errors="replace")


def make_aladin_chart(target, fov=1.0, survey="dss", catalog=None, grid=False,
                      width=1200, height=900, out=None):
    """Aladin chart with optional catalog overlay and coordinate grid."""
    out = Path(out).resolve() if out else default_out(target, "png")
    radius = f"{fov * 60:g}arcmin"
    lines = [f"get hips({resolve_survey(survey)}) {target} {radius}", "sync"]
    for cat in (catalog or []):
        if cat.lower() == "simbad":
            lines.append(f"get Simbad {target} {radius}")
        else:
            lines.append(f"get VizieR({cat}) {target} {radius}")
        lines.append("sync")
    if grid:
        lines.append("grid on")
    lines += [f"zoom {fov:g} deg", "sync",
              f"save -png {width}x{height} {out.as_posix()}", "quit"]
    rc, log = run_aladin_script("\n".join(lines))
    if not out.exists():
        raise RuntimeError(f"Aladin did not produce {out}\n--- log ---\n{log[-2000:]}")
    return out, log


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Aladin star-chart CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("chart", help="fast chart via hips2fits (no Aladin)")
    c.add_argument("target", help="object name or 'ra,dec' in degrees")
    c.add_argument("--fov", type=float, default=1.0, help="field of view, degrees")
    c.add_argument("--survey", default="dss", help="alias or full HiPS id")
    c.add_argument("--width", type=int, default=1200)
    c.add_argument("--height", type=int, default=900)
    c.add_argument("--projection", default="TAN", help="TAN SIN AIT MOL CAR STG ...")
    c.add_argument("--format", dest="fmt", default="png", choices=["png", "jpg", "fits"])
    c.add_argument("--out")

    a = sub.add_parser("aladin", help="chart via Aladin with catalog/grid overlays")
    a.add_argument("target")
    a.add_argument("--fov", type=float, default=1.0)
    a.add_argument("--survey", default="dss")
    a.add_argument("--catalog", action="append",
                   help="'simbad' or a VizieR id like I/355/gaiadr3; repeatable")
    a.add_argument("--grid", action="store_true")
    a.add_argument("--width", type=int, default=1200)
    a.add_argument("--height", type=int, default=900)
    a.add_argument("--out")

    s = sub.add_parser("script", help="run raw Aladin script (';' or newlines)")
    s.add_argument("commands", nargs="?", help="script text; omit to use --file")
    s.add_argument("--file", help="read script from file")
    s.add_argument("--timeout", type=int, default=300)

    sub.add_parser("surveys", help="list survey aliases")

    ns = ap.parse_args()
    if ns.cmd == "chart":
        out = make_chart(ns.target, ns.fov, ns.survey, ns.width, ns.height,
                         ns.projection, ns.fmt, ns.out)
        print(out)
    elif ns.cmd == "aladin":
        out, _ = make_aladin_chart(ns.target, ns.fov, ns.survey, ns.catalog,
                                   ns.grid, ns.width, ns.height, ns.out)
        print(out)
    elif ns.cmd == "script":
        text = Path(ns.file).read_text(encoding="utf-8") if ns.file else ns.commands
        if not text:
            ap.error("script: give commands or --file")
        rc, log = run_aladin_script(text.replace(";", "\n"), ns.timeout)
        print(log)
        sys.exit(rc)
    elif ns.cmd == "surveys":
        for k, v in SURVEYS.items():
            print(f"{k:14} {v}")


if __name__ == "__main__":
    main()
