#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aladin MCP server (stdio, zero dependencies).

Wraps aladin_cli: star charts via hips2fits, research charts via Aladin
Desktop headless mode. Register with:
  claude mcp add aladin -- python /path/to/mcp_server.py
or in claude_desktop_config.json:
  "aladin": {"command": "python", "args": ["/path/to/mcp_server.py"]}
"""
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aladin_cli

MAX_INLINE_IMAGE = 1_500_000  # bytes; larger images returned as path only

TOOLS = [
    {
        "name": "star_chart",
        "description": ("Make a star chart / sky image of any target from a HiPS survey "
                        "(via CDS hips2fits, fast). Returns the image inline plus its file path. "
                        "Survey aliases: " + ", ".join(aladin_cli.SURVEYS) + " — or any full HiPS id."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "object name (e.g. M31) or 'ra,dec' in degrees"},
                "fov": {"type": "number", "description": "field of view in degrees (default 1)"},
                "survey": {"type": "string", "description": "survey alias or HiPS id (default dss)"},
                "width": {"type": "integer"}, "height": {"type": "integer"},
                "projection": {"type": "string", "description": "TAN (default), SIN, AIT, MOL, CAR, STG"},
                "format": {"type": "string", "enum": ["png", "jpg", "fits"]},
            },
            "required": ["target"],
        },
    },
    {
        "name": "aladin_chart",
        "description": ("Research-grade chart via Aladin Desktop (headless): survey image with "
                        "optional coordinate grid and catalog overlays (Simbad or any VizieR id, "
                        "e.g. I/355/gaiadr3 for Gaia DR3). Slower (~10-30 s) but full-featured."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "object name or 'ra,dec' degrees"},
                "fov": {"type": "number", "description": "field of view in degrees (default 1)"},
                "survey": {"type": "string"},
                "catalogs": {"type": "array", "items": {"type": "string"},
                             "description": "'simbad' and/or VizieR ids to overlay"},
                "grid": {"type": "boolean", "description": "draw coordinate grid"},
                "width": {"type": "integer"}, "height": {"type": "integer"},
            },
            "required": ["target"],
        },
    },
    {
        "name": "aladin_script",
        "description": ("Run a raw Aladin script in headless Aladin Desktop for anything advanced: "
                        "RGB composition, contours, filters, crossmatch, MOC, multiple views. "
                        "Commands separated by newlines or ';'. Use absolute paths in 'save'. "
                        "Returns Aladin's console output."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "script": {"type": "string"},
                "timeout": {"type": "integer", "description": "seconds, default 300"},
            },
            "required": ["script"],
        },
    },
]


def image_result(path):
    content = [{"type": "text", "text": f"saved: {path}"}]
    data = Path(path).read_bytes()
    if path.suffix in (".png", ".jpg") and len(data) <= MAX_INLINE_IMAGE:
        mime = "image/png" if path.suffix == ".png" else "image/jpeg"
        content.append({"type": "image", "data": base64.b64encode(data).decode(), "mimeType": mime})
    return content


def call_tool(name, args):
    if name == "star_chart":
        out = aladin_cli.make_chart(
            args["target"], args.get("fov", 1.0), args.get("survey", "dss"),
            args.get("width", 1000), args.get("height", 750),
            args.get("projection", "TAN"), args.get("format", "png"))
        return image_result(out)
    if name == "aladin_chart":
        out, _ = aladin_cli.make_aladin_chart(
            args["target"], args.get("fov", 1.0), args.get("survey", "dss"),
            args.get("catalogs"), args.get("grid", False),
            args.get("width", 1000), args.get("height", 750))
        return image_result(out)
    if name == "aladin_script":
        rc, log = aladin_cli.run_aladin_script(
            args["script"].replace(";", "\n"), args.get("timeout", 300))
        return [{"type": "text", "text": log[-8000:] or "(no output)"}]
    raise ValueError(f"unknown tool {name}")


def main():
    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        mid = msg.get("id")
        method = msg.get("method", "")
        resp = None
        try:
            if method == "initialize":
                resp = {"protocolVersion": msg["params"].get("protocolVersion", "2024-11-05"),
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "aladin", "version": "1.0.0"}}
            elif method == "tools/list":
                resp = {"tools": TOOLS}
            elif method == "tools/call":
                content = call_tool(msg["params"]["name"], msg["params"].get("arguments", {}))
                resp = {"content": content, "isError": False}
            elif method == "ping":
                resp = {}
            elif mid is None:
                continue  # notification; nothing to answer
            else:
                stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid,
                                         "error": {"code": -32601, "message": f"method not found: {method}"}}).encode() + b"\n")
                stdout.flush()
                continue
        except Exception as e:
            if mid is not None:
                resp = {"content": [{"type": "text", "text": f"error: {e}"}], "isError": True}
                if method != "tools/call":
                    stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid,
                                             "error": {"code": -32603, "message": str(e)}}).encode() + b"\n")
                    stdout.flush()
                    continue
            else:
                continue
        if mid is not None:
            stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": resp}).encode() + b"\n")
            stdout.flush()


if __name__ == "__main__":
    main()
