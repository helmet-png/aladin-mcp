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


MAX_OVERLAYS = 8
OVERLAY_NAMES = [f"_ovl{i}" for i in range(MAX_OVERLAYS)]


def chart_script(target, fov, survey, catalog, grid, width, height, out):
    """Build the Aladin script that renders one chart to `out`.

    Catalog planes are given fixed names so a resident session can drop just
    those before the next chart. Image planes are deliberately left alone --
    they hold the cached tiles that make a warm session fast.
    """
    radius = f"{fov * 60:g}arcmin"
    catalog = (catalog or [])[:MAX_OVERLAYS]
    # Overlays and the grid persist across charts in a resident session, so
    # clear them explicitly rather than assuming a clean slate.
    lines = [f"rm {n}" for n in OVERLAY_NAMES]
    lines += [f"get hips({resolve_survey(survey)}) {target} {radius}", "sync"]
    for i, cat in enumerate(catalog):
        src = "Simbad" if cat.lower() == "simbad" else f"VizieR({cat})"
        lines.append(f"{OVERLAY_NAMES[i]} = get {src} {target} {radius}")
        lines.append("sync")
    lines.append("grid on" if grid else "grid off")
    lines += [f"zoom {fov:g} deg", "sync",
              f"save -png {width}x{height} {out.as_posix()}"]
    return lines


class AladinSession:
    """A resident headless Aladin process.

    Starting Aladin costs ~5 s of JVM and class loading before any work
    happens, and a fresh process also throws away the resolved HiPS registry
    and the in-memory tile cache. Keeping one process alive across charts
    turns a ~16 s render into ~3-6 s. Completion is detected by watching for
    the output file, since Aladin's console output is not a reliable signal.
    """

    def __init__(self):
        self.proc = None

    def _alive(self):
        return self.proc is not None and self.proc.poll() is None

    def start(self):
        if self._alive():
            return
        java = os.environ.get("JAVA_BIN") or shutil.which("java")
        if not java:
            raise FileNotFoundError("java not found on PATH; set JAVA_BIN.")
        self.proc = subprocess.Popen(
            [java, "-jar", find_aladin_jar(), "-nogui", "-script"],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, bufsize=0)

    def render(self, lines, out, timeout=300):
        """Run a script ending in `save <out>`; wait for the file to appear."""
        out = Path(out)
        if out.exists():
            out.unlink()
        self.start()
        script = "\n".join(lines) + "\nsync\n"
        try:
            self.proc.stdin.write(script.encode("utf-8"))
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError):
            self.close()          # process died; retry once on a fresh one
            self.start()
            self.proc.stdin.write(script.encode("utf-8"))
            self.proc.stdin.flush()

        deadline = time.time() + timeout
        while time.time() < deadline:
            if not self._alive():
                raise RuntimeError("Aladin exited unexpectedly while rendering.")
            if out.exists() and out.stat().st_size > 0:
                time.sleep(0.4)   # let the write finish
                return out
            time.sleep(0.2)
        raise TimeoutError(f"Aladin did not produce {out} within {timeout}s.")

    def close(self):
        if self._alive():
            try:
                self.proc.stdin.write(b"quit\n")
                self.proc.stdin.flush()
                self.proc.wait(timeout=15)
            except Exception:
                self.proc.kill()
        self.proc = None


def make_aladin_chart(target, fov=1.0, survey="dss", catalog=None, grid=False,
                      width=1200, height=900, out=None, session=None):
    """Aladin chart with optional catalog overlay and coordinate grid.

    Pass a live `session` to reuse a resident Aladin and skip startup cost.
    """
    out = Path(out).resolve() if out else default_out(target, "png")
    lines = chart_script(target, fov, survey, catalog, grid, width, height, out)
    if session is not None:
        return session.render(lines, out), ""
    rc, log = run_aladin_script("\n".join(lines + ["quit"]))
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

    b = sub.add_parser("batch", help="several Aladin charts in one resident process (much faster)")
    b.add_argument("targets", nargs="+")
    b.add_argument("--fov", type=float, default=1.0)
    b.add_argument("--survey", default="dss")
    b.add_argument("--catalog", action="append")
    b.add_argument("--grid", action="store_true")
    b.add_argument("--width", type=int, default=1200)
    b.add_argument("--height", type=int, default=900)

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
    elif ns.cmd == "batch":
        session = AladinSession()
        try:
            for t in ns.targets:
                out, _ = make_aladin_chart(t, ns.fov, ns.survey, ns.catalog,
                                           ns.grid, ns.width, ns.height,
                                           session=session)
                print(out, flush=True)
        finally:
            session.close()
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
