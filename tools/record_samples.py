"""Record screen samples of Diablo II: Resurrected for calibration and bug reports.

    python tools/record_samples.py [minutes] [output folder]      (default: 20 minutes, ./samples/<date-time>)

Play normally while it runs: level up at least once without spending the points right away, and
open the character screen (C) a few times. Works at any resolution, fullscreen or windowed, on
any monitor: it finds the game window by its process (D2R.exe) and records only while the game
is the foreground window.

What it does: copies three small parts of the SCREEN (like Print Screen) and saves them as PNG
when something changes: the XP bar strip at the bottom (with the level-up buttons above it) and
the top of the character screen. It never opens or touches the game process, its memory or its
files, and sends nothing anywhere. Requires Python 3 with Pillow and NumPy.

The regions are defined on a 2560 x 1440 reference and scaled to the game's client area, with a
margin, so the same script serves every 16:9 resolution. Each sample folder gets an info.json
with the client size and position.
"""
import ctypes
import ctypes.wintypes as wt
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import ImageGrab

user32 = ctypes.windll.user32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)      # per-monitor aware: real pixels
except Exception:
    user32.SetProcessDPIAware()

# reference (2560 x 1440) regions, left, top, right, bottom
REGIONS = {
    "bottom": (500, 1000, 2060, 1350),   # level-up buttons + XP bar
    "panel": (200, 170, 880, 340),       # top of the character screen (title, level line, XP numbers)
}


def d2r_pids():
    """Process ids of D2R.exe, from a process snapshot (no handle to the game is opened)."""
    TH32CS_SNAPPROCESS = 0x2

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wt.DWORD), ("cntThreads", wt.DWORD),
                    ("th32ParentProcessID", wt.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
                    ("szExeFile", ctypes.c_wchar * 260)]

    k32 = ctypes.windll.kernel32
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    pids = set()
    e = PROCESSENTRY32W()
    e.dwSize = ctypes.sizeof(e)
    ok = k32.Process32FirstW(snap, ctypes.byref(e))
    while ok:
        if e.szExeFile.lower() == "d2r.exe":
            pids.add(e.th32ProcessID)
        ok = k32.Process32NextW(snap, ctypes.byref(e))
    k32.CloseHandle(snap)
    return pids


def game_client():
    """(left, top, width, height) of the game's client area when D2R is the foreground window, else None."""
    h = user32.GetForegroundWindow()
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
    if pid.value not in d2r_pids():
        return None
    r = wt.RECT()
    user32.GetClientRect(h, ctypes.byref(r))
    p = wt.POINT(0, 0)
    user32.ClientToScreen(h, ctypes.byref(p))
    return p.x, p.y, r.right - r.left, r.bottom - r.top


def scaled(region, client, margin=12):
    x0, y0, w, h = client
    s = h / 1440.0
    ox = x0 + (w - 2560 * s) / 2          # 16:9 area centred in the client (wider screens: bars at the sides)
    l, t, r, b = region
    return (int(ox + (l - margin) * s), int(y0 + (t - margin) * s), int(ox + (r + margin) * s), int(y0 + (b + margin) * s))


def main():
    minutes = float(sys.argv[1]) if len(sys.argv) > 1 else 20
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("samples") / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    end = time.time() + minutes * 60
    last = {}
    last_save = 0
    saved = 0
    clients = set()
    print(f"recording for {minutes:g} min into {out} (Ctrl+C stops)")
    while time.time() < end:
        t0 = time.time()
        c = game_client()
        if c is None:
            time.sleep(1)
            continue
        if c not in clients:
            clients.add(c)
            print(f"game client area: {c[2]}x{c[3]} at ({c[0]},{c[1]})")
            (out / "info.json").write_text(json.dumps({"clients": sorted(clients)}, indent=1), encoding="utf-8")
        shots = {k: ImageGrab.grab(bbox=scaled(r, c), all_screens=True) for k, r in REGIONS.items()}
        small = {k: np.asarray(im.convert("L").resize((96, 24)), dtype=np.int16) for k, im in shots.items()}
        changed = [k for k in shots if k not in last or np.abs(small[k] - last[k]).mean() > 6]
        if changed or time.time() - last_save > 10:
            stamp = datetime.now().strftime("%H%M%S_%f")[:9]
            for k, im in shots.items():
                im.save(out / f"{stamp}_{c[2]}x{c[3]}_{k}.png")
                last[k] = small[k]
            last_save = time.time()
            saved += 1
        time.sleep(max(0, 0.5 - (time.time() - t0)))
    print(f"done: {saved} samples in {out}")


if __name__ == "__main__":
    main()
