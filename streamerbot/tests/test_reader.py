"""Tests for the reader and the level-up rules, running the real C# (the same code that goes
into the .sb) outside Streamer.bot.

    python streamerbot/tests/test_reader.py

1. fixtures: real screen captures in tests/fixtures/<width>x<height>/, four regions each
   (xpline, stats, skill, hud), checked against expected.json;
2. the 2560x1440 fixtures resized to 1920x1080 and 3840x2160 (the resize path of the action);
3. the level-up rules (Tracker) on tick sequences, including the real level-ups recorded;
4. the safety check of build.py refuses code that touches another process.
Needs the .NET Framework compiler (csc.exe, part of Windows) and Python with Pillow + NumPy.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import build  # noqa: E402

REGIONS = {"xpline": (320, 23), "stats": (81, 80), "skill": (81, 80), "hud": (1033, 38)}

PROGRAM = r'''
public static class Test
{
    public static void Main(string[] args)
    {
        System.Console.OutputEncoding = new System.Text.UTF8Encoding(false);
        if (args[0] == "fixtures")
        {
            string dir = args[1];
            double scale = double.Parse(args[2], System.Globalization.CultureInfo.InvariantCulture);
            var regs = Regions.All;
            var names = new[] { "xpline", "stats", "skill", "hud" };
            for (int k = 3; k < args.Length; k++)
            {
                var imgs = new Img[4];
                for (int i = 0; i < 4; i++)
                    using (var bmp = new System.Drawing.Bitmap(dir + "\\" + args[k] + "_" + names[i] + ".png"))
                        imgs[i] = Img.FromBitmapResized(bmp, regs[i].Width, regs[i].Height);
                var r = Reader.Read(imgs[0], imgs[1], imgs[2], imgs[3], scale);
                System.Console.WriteLine(args[k] + "|" + (r.Hud ? 1 : 0) + "|" + r.Xp.ToString("0.000", System.Globalization.CultureInfo.InvariantCulture)
                    + "|" + (r.NewStats ? 1 : 0) + "|" + (r.NewSkill ? 1 : 0) + "|" + r.PanelLevel + "|" + r);
            }
            return;
        }
        // sequences: "# name startLevel", then "seconds hud xp stats skill panelLevel"
        Tracker t = null;
        var t0 = new System.DateTime(2026, 11, 14, 15, 0, 0);
        foreach (var raw in System.IO.File.ReadAllLines(args[1]))
        {
            var s = raw.Trim();
            if (s == "") continue;
            if (s.StartsWith("#"))
            {
                var p = s.Substring(1).Trim().Split(' ');
                t = new Tracker(); t.Level = int.Parse(p[1]);
                System.Console.WriteLine("CASE|" + p[0]);
                continue;
            }
            var c = s.Split(' ');
            var r = new Reading { Hud = c[1] == "1", Xp = double.Parse(c[2], System.Globalization.CultureInfo.InvariantCulture),
                                  NewStats = c[3] == "1", NewSkill = c[4] == "1", PanelLevel = int.Parse(c[5]) };
            string why;
            var ev = t.Step(r, t0.AddSeconds(double.Parse(c[0], System.Globalization.CultureInfo.InvariantCulture)), out why);
            if (ev != null || why != null) System.Console.WriteLine("EV|" + c[0] + "|" + (ev ?? "-") + "|" + t.Level + "|" + why);
        }
    }
}
'''

SEQUENCES = """
# real_up_to_59 58
0 1 0.88 0 0 -1
1 1 0.90 0 0 -1
2 1 0.91 0 0 -1
3 1 0.91 1 1 -1
4 1 0.02 1 1 -1
5 1 0.09 1 1 -1
# real_up_to_61_live 60
0 1 0.986 0 0 -1
1 1 0.990 0 0 -1
2 1 0.997 1 1 -1
3 1 0.020 1 1 -1
4 1 0.020 1 1 -1
# up_with_character_screen_open 59
0 1 0.93 0 0 -1
1 1 0.94 0 0 -1
2 1 0.00 1 1 -1
3 1 0.00 0 1 60
4 1 0.01 0 1 60
# up_with_character_screen_and_skill_tree 59
0 1 0.97 0 0 59
1 1 0.98 0 0 59
2 1 0.01 0 0 60
3 1 0.02 0 0 60
# buttons_alone_do_not_count 59
0 1 0.40 0 0 -1
1 1 0.40 1 0 -1
2 1 0.41 1 1 -1
3 1 0.41 0 0 -1
4 1 0.41 1 1 -1
# something_on_top_of_the_bar 59
0 1 0.81 1 0 -1
1 1 0.81 1 0 -1
2 1 0.30 1 0 -1
3 1 0.81 1 0 -1
# one_tick_drop 59
0 1 0.81 1 0 -1
1 1 0.10 1 0 -1
2 1 0.81 1 0 -1
# loading_screen 59
0 1 0.70 1 1 -1
1 0 0.00 0 0 -1
2 0 0.00 0 0 -1
3 1 0.70 1 1 -1
4 1 0.70 1 1 -1
# other_character 60
0 1 0.80 0 0 -1
1 0 0 0 0 -1
40 0 0 0 0 -1
41 1 0.10 1 1 -1
42 1 0.10 1 1 -1
# quick_character_switch 60
0 1 0.80 0 0 -1
1 0 0 0 0 -1
5 1 0.10 1 1 -1
6 1 0.10 1 1 -1
# death_in_hell 60
0 1 0.50 0 0 -1
1 1 0.45 0 0 -1
2 1 0.45 0 0 -1
# no_sign_then_character_screen 60
0 1 0.95 0 0 -1
1 1 0.02 0 0 -1
2 1 0.02 0 0 -1
20 1 0.03 0 0 61
# level_unknown -1
0 1 0.95 0 0 -1
1 1 0.02 1 1 -1
2 1 0.02 1 1 -1
10 1 0.03 0 0 61
# two_level_ups 30
0 1 0.95 0 0 -1
1 1 0.02 1 1 -1
2 1 0.02 1 1 -1
30 1 0.97 1 1 -1
31 1 0.01 1 1 -1
32 1 0.02 1 1 -1
# glow_frame 60
0 1 0.94 0 0 -1
1 1 0.94 0 0 -1
2 1 1.00 1 1 -1
3 1 0.00 1 1 -1
4 1 0.01 1 1 -1
# hud_gone_for_a_second 60
0 1 0.94 0 0 -1
1 0 0.00 1 1 -1
2 1 0.00 1 1 -1
3 1 0.01 1 1 -1
# character_screen_corrects 58
0 1 0.30 0 0 -1
1 1 0.30 0 0 60
"""
EVENTS = {
    "real_up_to_59": [("up", 59)], "real_up_to_61_live": [("up", 61)], "up_with_character_screen_open": [("up", 60)],
    "up_with_character_screen_and_skill_tree": [("up", 60)], "buttons_alone_do_not_count": [],
    "something_on_top_of_the_bar": [], "one_tick_drop": [], "loading_screen": [], "other_character": [],
    "quick_character_switch": [], "death_in_hell": [], "no_sign_then_character_screen": [("-", 60), ("up", 61)],
    "level_unknown": [("-", -1), ("corrected", 61)], "two_level_ups": [("up", 31), ("up", 32)],
    "glow_frame": [("up", 61)],
    "hud_gone_for_a_second": [("up", 61)], "character_screen_corrects": [("corrected", 60)],
    "session_1920x1080": [("corrected", 62), ("up", 63), ("up", 64)],   # fixtures/sessions: a whole recorded session
}


def resized(src, dst, scale):
    dst.mkdir(parents=True, exist_ok=True)
    for f in src.glob("*.png"):
        im = Image.open(f).convert("RGB")
        w, h = REGIONS[f.stem.rsplit("_", 1)[1]]
        im.resize((round(w * scale), round(h * scale)), Image.BILINEAR).save(dst / f.name)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    fails = total = 0
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cs = tmp / "t.cs"
        cs.write_text(build.reader_source() + PROGRAM, encoding="utf-8")
        exe = tmp / "t.exe"
        r = subprocess.run([str(build.FW / "csc.exe"), "/nologo", "/codepage:65001", f"/out:{exe}",
                            f"/reference:{build.FW / 'System.Drawing.dll'}", str(cs)], capture_output=True, text=True, encoding="cp850")
        if r.returncode:
            sys.exit(r.stdout)

        def run(*a):
            p = subprocess.run([str(exe), *map(str, a)], capture_output=True, text=True, encoding="utf-8")
            if p.returncode:
                sys.exit(p.stdout + p.stderr)
            return p.stdout.strip().splitlines()

        sets = []
        for d in sorted((HERE / "fixtures").glob("*x*")):            # fixtures/<width>x<height>
            w, h = map(int, d.name.split("x"))
            sets.append((d.name + " (real)", d, h / 1440, json.loads((d / "expected.json").read_text(encoding="utf-8"))))
        base = HERE / "fixtures" / "2560x1440"
        for name, scale in (("1920x1080", 0.75), ("3840x2160", 1.5)):
            resized(base, tmp / name, scale)
            sets.append((name + " (2560x1440 resized)", tmp / name, scale, json.loads((base / "expected.json").read_text(encoding="utf-8"))))
        for title, d, scale, expected in sets:
            print(f"-- {title}")
            for line in run("fixtures", d, scale, *expected):
                name, hud, xp, st, sk, lvl, txt = line.split("|")
                got = (int(hud), float(xp), int(st), int(sk), int(lvl))
                e = expected[name]
                want = (e["hud"], e["xp"], e["newStats"], e["newSkill"], e["level"])
                ok = all(w is None or (abs(w - g) < 0.03 if i == 1 else w == g) for i, (w, g) in enumerate(zip(want, got)))
                fails += not ok
                total += 1
                print(("ok  " if ok else "FAIL"), f"{name:16} {txt}   [{e['note']}]")

        seq = tmp / "seq.txt"
        sessions = ""
        for f in sorted((HERE / "fixtures" / "sessions").glob("*.txt")):     # whole recorded sessions
            keep = [l for l in f.read_text(encoding="utf-8").splitlines() if not l.startswith("# ") or l.startswith("# session")]
            sessions += "\n".join(keep) + "\n"
        seq.write_text(SEQUENCES + sessions, encoding="utf-8")
        print("-- level-up rules")
        cases, cur = {}, None
        for line in run("seq", seq):
            p = line.split("|")
            if p[0] == "CASE":
                cur = p[1]; cases[cur] = []
            else:
                cases[cur].append((p[2], int(p[3]), p[4]))
        for name, want in EVENTS.items():
            got = cases.get(name, [])
            ok = [(e, n) for e, n, _ in got] == want
            fails += not ok
            total += 1
            print(("ok  " if ok else "FAIL"), f"{name:40}", "; ".join(f"{e} {n} ({m})" for e, n, m in got) or "nothing")

    print("-- safety check")
    for bad in ('[System.Runtime.InteropServices.DllImport("kernel32.dll")] static extern System.IntPtr OpenProcess(int a, bool b, int c);',
                "var m = System.Diagnostics.Process.GetProcessesByName(\"D2R\")[0].MainModule;", "CPH.SendMessage(\"hi\");"):
        try:
            build.check_safety(bad)
            ok = False
        except SystemExit:
            ok = True
        fails += not ok
        total += 1
        print(("ok  " if ok else "FAIL"), "refuses:", bad[:70])
    print(f"\n{total - fails} of {total} passed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
