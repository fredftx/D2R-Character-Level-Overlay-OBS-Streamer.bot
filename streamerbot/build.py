"""Build the Streamer.bot import file from src/*.cs and templates/*.png.

    python streamerbot/build.py            # check, compile and write streamerbot/D2R-Level-Overlay.sb
    python streamerbot/build.py --source   # also write build/D2RLevel.cs (the code as Streamer.bot gets it)

Steps:
1. fills the templates into src/Reader.cs (base64);
2. **refuses** to build if the code uses anything that could touch another process or send
   input (see FORBIDDEN and ALLOWED_IMPORTS) — the promise in the README is checked here, on
   every build, not just written down;
3. compiles it with the .NET Framework compiler against Streamer.bot.Plugin.Interface.dll
   (folder from STREAMERBOT_DIR, default D:\\Streamer.bot; skipped with a warning if absent);
4. writes the import string (.sb) with one action, "D2R Level", and the !level command.

Requires Python 3 with Pillow and NumPy.
"""
import base64
import gzip
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
SRC, TEMPLATES = HERE / "src", HERE / "templates"
OUT = HERE / "D2R-Level-Overlay.sb"
FW = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Microsoft.NET" / "Framework64" / "v4.0.30319"
SB_DIR = Path(os.environ.get("STREAMERBOT_DIR", r"D:\Streamer.bot"))
REFERENCES = [str(FW / n) for n in ("mscorlib.dll", "System.dll", "System.Core.dll", "System.Drawing.dll")]
VERSION = "1.0.0"
ACTION, GROUP, COMMAND = "D2R Level", "D2R Level Overlay", "!level"

# Nothing that opens, reads, writes or injects into another process, or simulates input.
FORBIDDEN = ["OpenProcess", "ReadProcessMemory", "WriteProcessMemory", "VirtualAlloc", "VirtualProtect",
             "CreateRemoteThread", "NtQuery", "NtRead", "SetWindowsHookEx", "SendInput", "keybd_event",
             "mouse_event", "PostMessage", "SendMessage", "SetForegroundWindow", "AttachThreadInput",
             "DuplicateHandle", "MiniDumpWriteDump", "DebugActiveProcess", "LoadLibrary", "GetProcAddress",
             ".MainModule", ".Modules", ".Handle", ".MainWindowHandle", ".StartTime", ".TotalProcessorTime",
             ".Kill(", "Process.Start", "File.", "Directory.", "Registry", "WebClient", "HttpClient", "WebRequest"]
ALLOWED_IMPORTS = {"GetForegroundWindow", "GetWindowThreadProcessId", "GetClientRect", "ClientToScreen",
                   "SetThreadDpiAwarenessContext"}


def gray(name):
    return np.asarray(Image.open(TEMPLATES / name).convert("RGB")).astype(int).sum(axis=2) // 3


def b64(arr):
    return base64.b64encode(np.asarray(arr, dtype=np.uint8).tobytes()).decode()


def reader_source():
    """src/Reader.cs with the templates filled in (also used by the tests)."""
    reader = (SRC / "Reader.cs").read_text(encoding="utf-8")
    digits, widths = [], []
    for d in range(10):
        m = gray(f"digit_{d}.png") > 127
        assert m.shape[0] == 12, f"digit_{d}.png must be 12 px tall"
        widths.append(m.shape[1])
        digits.append(m.T.reshape(-1))                   # column by column
    fill = {"HUD_FRAME": b64(gray("hud_frame.png")), "ICON_NEW_STATS": b64(gray("icon_new_stats.png")),
            "ICON_NEW_SKILL": b64(gray("icon_new_skill.png")), "DIGITS": b64(np.concatenate(digits)),
            "DIGIT_WIDTHS": ", ".join(map(str, widths))}
    for k, v in fill.items():
        reader = reader.replace(f"%{k}%", v)
    left = re.findall(r"%[A-Z_]+%", reader)
    assert not left, f"template markers left: {left}"
    return reader


def source():
    action = (SRC / "Action.cs").read_text(encoding="utf-8")
    return f"// D2R Level Overlay {VERSION} - https://github.com/fredftx/D2R-Character-Level-Overlay-OBS-Streamer.bot\n" + action + "\n" + reader_source()


def check_safety(code):
    # comments may mention forbidden names (to say they are not used); check code only
    bare = re.sub(r"//[^\n]*", "", code)
    bad = [w for w in FORBIDDEN if w in bare]
    imports = set(re.findall(r"DllImport\([^)]*\)\]\s*static\s+extern\s+[\w.]+\s+(\w+)\s*\(", bare))
    extra = imports - ALLOWED_IMPORTS
    if bad or extra:
        sys.exit(f"REFUSED: the code uses {sorted(bad) + sorted(extra)} - see FORBIDDEN/ALLOWED_IMPORTS in build.py")
    if len(re.findall(r"DllImport", bare)) != len(imports):
        sys.exit("REFUSED: a DllImport that this check could not read")
    print(f"safety check: OK (Windows calls: {', '.join(sorted(imports))}; nothing that touches another process)")


def compile_check(code):
    iface = SB_DIR / "Streamer.bot.Plugin.Interface.dll"
    if not iface.exists():
        print(f"WARNING: {iface} not found (set STREAMERBOT_DIR); skipped the compile check")
        return
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "a.cs"
        f.write_text(code.replace("public class CPHInline\n", "public class CPHInline : Streamer.bot.Plugin.Interface.CPHInlineBase\n"),
                     encoding="utf-8")
        r = subprocess.run([str(FW / "csc.exe"), "/nologo", "/target:library", "/codepage:65001", f"/out:{Path(tmp) / 'a.dll'}",
                            f"/reference:{iface}", f"/reference:{FW / 'System.Drawing.dll'}", str(f)],
                           capture_output=True, text=True, encoding="cp850")
        if r.returncode:
            sys.exit("compile errors:\n" + r.stdout)
    print("compile check: OK")


def uid(*parts):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "d2r-level-overlay/" + "/".join(parts)))


def package(code):
    action = {
        "id": uid(ACTION), "queue": None, "enabled": True, "excludeFromHistory": True,
        "name": ACTION, "group": GROUP, "alwaysRun": False, "randomAction": False, "concurrent": True,
        "triggers": [{"id": uid(ACTION, "trigger", "706"), "type": 706, "enabled": True, "exclusions": []},   # Streamer.bot Started
                     {"commandId": uid("command", COMMAND), "id": uid(ACTION, "trigger", COMMAND), "type": 401,
                      "enabled": True, "exclusions": []}],
        "actions": [{
            "name": "", "description": "", "references": REFERENCES,
            "byteCode": base64.b64encode(code.encode("utf-8")).decode(),
            "precompile": True, "delayStart": False, "saveResultToVariable": False, "saveToVariable": "",
            "id": uid(ACTION, "code"), "weight": 0.0, "type": 99999, "group": None, "enabled": True, "index": 0,
        }],
        "actionGroups": [], "collapsedGroups": [],
    }
    command = {
        "sources": [0], "permittedUsers": [], "permittedGroups": [],
        "id": uid("command", COMMAND), "name": f"D2R Level {COMMAND}", "enabled": True, "include": True, "mode": 0,
        "command": COMMAND, "regexExplicitCapture": False, "location": 0, "ignoreBotAccount": True,
        "ignoreInternal": False, "persistCounter": False, "persistUserCounter": False, "caseSensitive": False,
        "globalCooldown": 0, "userCooldown": 0, "group": GROUP, "grantType": 0,
    }
    data = {
        "meta": {"name": "D2R Level Overlay", "author": "FredFTX", "version": VERSION,
                 "description": "Diablo II: Resurrected character level read from the screen, for an OBS overlay.",
                 "autoRunAction": None, "minimumVersion": None},
        "data": {"actions": [action], "queues": [], "commands": [command],
                 "websocketServers": [], "websocketClients": [], "timers": []},
        "version": 10, "exportedFrom": "0.2.4", "minimumVersion": "0.2.4-beta.6",
    }
    raw = b"SBAE" + gzip.compress(json.dumps(data, ensure_ascii=False).encode("utf-8"))
    return base64.b64encode(raw).decode()


def main():
    code = source()
    check_safety(code)
    compile_check(code)
    if "--source" in sys.argv:
        (HERE.parent / "build").mkdir(exist_ok=True)
        (HERE.parent / "build" / "D2RLevel.cs").write_text(code, encoding="utf-8")
    OUT.write_text(package(code), encoding="ascii")
    print(f"wrote {OUT.relative_to(HERE.parent)} ({len(code) // 1024} KB of C#, version {VERSION})")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
