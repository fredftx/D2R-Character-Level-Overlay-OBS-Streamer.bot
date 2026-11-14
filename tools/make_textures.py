"""Make the Diablo II textures for the overlay from YOUR OWN screenshots of the game.

    python tools/make_textures.py --character panel.png --gold gold.png --hud-low low.png --hud-high high.png --screen game.png

The textures are pieces of Blizzard's game art. They are NOT shipped with this project: each
streamer makes them from screenshots of their own game, and they stay on that PC
(overlay/textures/ is ignored by git). Without them, the Diablo II presets use the look drawn in
code; with them, the overlay uses the game's own stone, frames, XP bar and globes.

Inputs:
  --character  the character screen (C), cropped to the panel (~747 x 992 from a 1440p screen)
  --gold       the gold counter box at the bottom of the stash/vendor window (~768 x 141)
  --hud-low    the XP-bar strip right after a level up (bar almost empty): a "_xp" sample of
               tools/record_samples.py at 2560 x 1440 (origin 740,1300 on screen)
  --hud-high   the same strip with the bar almost full, over a different background
  --screen     a whole game screenshot (any 16:9 size) with full life and mana globes

Outputs (--out, default overlay/textures): stone.png, stone_dark.png, frame.png (9-slice, 34 px),
slot.png (9-slice, 8 px), goldbox.png (9-slice, 14 px), bar_empty.png, bar_fill.png, orb_life.png,
orb_mana.png and textures.json.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps


def mirror_x(im, times=3):
    """Horizontal strip of the image and its mirror, repeated: tiles without seams sideways."""
    w, h = im.size
    t = Image.new(im.mode, (w * 2 * times, h))
    for k in range(times):
        t.paste(im, (2 * k * w, 0))
        t.paste(ImageOps.mirror(im), ((2 * k + 1) * w, 0))
    return t


def nine_slice(src, corner_box, edge_h_box, edge_v_box, b, inner, size=160):
    """Clean 9-slice source from the top-left corner and edge pieces of a real frame, mirrored
    to the other sides, with `inner` in the middle."""
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    c = src.crop(corner_box).resize((b, b))
    eh, ev = src.crop(edge_h_box), src.crop(edge_v_box)
    top = Image.new("RGBA", (size - 2 * b, b))
    for x in range(0, top.width, eh.width):
        top.paste(eh, (x, 0))
    left = Image.new("RGBA", (b, size - 2 * b))
    for y in range(0, left.height, ev.height):
        left.paste(ev, (0, y))
    out.paste(inner.resize((size - 2 * b, size - 2 * b)), (b, b))
    out.paste(c, (0, 0)); out.paste(ImageOps.mirror(c), (size - b, 0))
    out.paste(ImageOps.flip(c), (0, size - b)); out.paste(ImageOps.flip(ImageOps.mirror(c)), (size - b, size - b))
    out.paste(top, (b, 0)); out.paste(ImageOps.flip(top), (b, size - b))
    out.paste(left, (0, b)); out.paste(ImageOps.mirror(left), (size - b, b))
    return out


def box9(src, b, size=(64, 48), inner=None, edge_x=None):
    """9-slice source from a whole box image: its four corners and edges, `inner` (or the
    box's own middle) inside. edge_x = (x0, x1): take the top and bottom edges from there only
    (a plain stretch, away from light spots near the corners)."""
    w, h = src.size
    W, H = size
    ex0, ex1 = edge_x or (b, w - b)
    out = Image.new("RGBA", size)
    out.paste((inner or src.crop((b, b, w - b, h - b))).resize((W - 2 * b, H - 2 * b)), (b, b))
    out.paste(src.crop((ex0, 0, ex1, b)).resize((W - 2 * b, b)), (b, 0))
    out.paste(src.crop((ex0, h - b, ex1, h)).resize((W - 2 * b, b)), (b, H - b))
    out.paste(src.crop((0, b, b, h - b)).resize((b, H - 2 * b)), (0, b))
    out.paste(src.crop((w - b, b, w, h - b)).resize((b, H - 2 * b)), (W - b, b))
    for (sx, sy, dx, dy) in ((0, 0, 0, 0), (w - b, 0, W - b, 0), (0, h - b, 0, H - b), (w - b, h - b, W - b, H - b)):
        out.paste(src.crop((sx, sy, sx + b, sy + b)), (dx, dy))
    return out


def globe(screen, cx, cy, r):
    """Circle of a globe (fractions of the screen), transparent outside."""
    W, H = screen.size
    x, y, rad = cx * W, cy * H, r * H
    crop = screen.crop((round(x - rad), round(y - rad), round(x + rad), round(y + rad))).convert("RGBA")
    mask = Image.new("L", crop.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, crop.width - 1, crop.height - 1), fill=255)
    crop.putalpha(mask)
    return crop.resize((160, 160), Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    for a in ("character", "gold", "hud-low", "hud-high", "screen"):
        ap.add_argument("--" + a, required=True)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "overlay" / "textures"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    char = Image.open(args.character).convert("RGBA")
    gold = Image.open(args.gold).convert("RGBA")

    # stones: light (panel header, between the corner ornament and the title) and dark (panel body)
    mirror_x(char.crop((96, 40, 290, 84))).save(out / "stone.png")
    mirror_x(char.crop((50, 304, 226, 432))).save(out / "stone_dark.png")
    # engraved window frame: corner and diamond band from the top-left of the panel
    nine_slice(char, (0, 0, 34, 34), (40, 0, 59, 34), (0, 40, 34, 59), 34, char.crop((96, 40, 290, 84))).save(out / "frame.png")
    # sunken value box (an empty box of the right column) and the gold-trimmed box (without the coin)
    box9(char.crop((350, 362, 712, 412)), 8).save(out / "slot.png")
    g = gold.crop((250, 20, 504, 84))                # stone rim + thin gold trim + sunken inside
    box9(g, 14, size=(96, 64), inner=g.crop((175, 16, 235, 46)), edge_x=(170, 236)).save(out / "goldbox.png")

    # HUD XP bar (2560 x 1440 samples, origin 740,1300): screen x 765..1800, y 1306..1339
    lo = np.asarray(Image.open(args.hud_low).convert("RGB")).astype(int)[6:40, 25:1061]
    hi = np.asarray(Image.open(args.hud_high).convert("RGB")).astype(int)[6:40, 25:1061]
    h, w = lo.shape[:2]
    tx0, tx1, ty0, ty1 = 11, 1028, 16, 27            # the track (where the fill goes)
    seg = (tx1 - tx0 + 1) / 10.0
    top = 3                                          # rows above the frame (y 1306-1308): only the spikes are bar
    keep = np.zeros(w, bool)
    for k in range(9):                               # spike centres measured on the 1440p HUD: x 107 + 102.07 k
        c = round(107 + 102.07 * k)
        keep[c - 4:c + 5] = True
    static = np.abs(lo[:top] - hi[:top]).sum(axis=2) < 40   # same pixel over two backgrounds = the bar's own
    alpha = np.full((h, w), 255, np.uint8)
    alpha[:top] = np.where(keep[None, :] & static, 255, 0)
    empty = lo.copy()
    a = int(tx0 + seg + 4)                           # segment 2 is empty: paint it over the start of segment 1
    n = int(seg) - 4
    empty[ty0:ty1, tx0 - 2:tx0 - 2 + n] = lo[ty0:ty1, a - 3:a - 3 + n]   # from just before the track (the fill's glow starts there)
    Image.fromarray(np.dstack([empty.astype(np.uint8), alpha])).save(out / "bar_empty.png")
    full = hi.copy()
    s9 = int(tx0 + seg * 8)                          # segment 9 is full: copy it onto segment 10
    full[ty0:ty1, s9 + int(seg):tx1 + 1] = hi[ty0:ty1, s9:s9 + (tx1 + 1 - s9 - int(seg))]
    fa = np.zeros((h, w), np.uint8)
    fa[ty0:ty1, tx0:tx1 + 1] = 255
    Image.fromarray(np.dstack([full.astype(np.uint8), fa])).save(out / "bar_fill.png")

    # globes: circles inside the life (left) and mana (right) globes, away from the statues' hands
    screen = Image.open(args.screen).convert("RGB")
    globe(screen, 0.2475, 0.9227, 0.0658).save(out / "orb_life.png")
    globe(screen, 0.7515, 0.9227, 0.0658).save(out / "orb_mana.png")

    (out / "textures.json").write_text(json.dumps({"bar": {"w": w, "h": h, "trackX0": tx0, "trackX1": tx1},
                                                   "frame": 34, "slot": 8, "goldbox": 14}, indent=1), encoding="utf-8")
    print("textures written to", out)


if __name__ == "__main__":
    main()
