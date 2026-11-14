// D2R Level Overlay — screen reader (pure logic, no Streamer.bot and no Windows calls here).
//
// Everything is measured on a 2560 x 1440 reference screen. The Streamer.bot action copies four
// small rectangles of the SCREEN (scaled to the game's resolution), resizes them to the
// reference size and hands them to Reader.Read. Nothing here knows the game's language:
//   - XP bar of the HUD: how far the white fill goes = progress inside the current level;
//   - HUD frame: the metal frame around the XP bar is static art; if it does not match, the HUD
//     is not on screen (loading, menus, something on top) and the tick is ignored;
//   - level-up buttons: the red squares with the golden cross above the HUD (the "New Stats" /
//     "New Skill" buttons) — matched as pictures, never as words;
//   - character screen: the XP line ends, right-aligned, with the experience needed for the next
//     level ("... of 128,782,495"). Reading that number and finding it in the Diablo II
//     experience table gives the exact level, whatever the language of the word "Level".
// Tracker turns readings into "level up" events (see the rules in its comments).
//
// Templates (the placeholders between percent signs) are filled in by build.py from streamerbot/templates/*.png.

public sealed class Img
{
    public readonly int W, H;
    public readonly byte[] P;          // RGB, 3 bytes per pixel, row by row
    public Img(int w, int h) { W = w; H = h; P = new byte[w * h * 3]; }
    public int Gray(int x, int y) { int i = (y * W + x) * 3; return (P[i] + P[i + 1] + P[i + 2]) / 3; }
    public bool White(int x, int y) { int i = (y * W + x) * 3; return P[i] > 200 && P[i + 1] > 200 && P[i + 2] > 150; }

    public static Img FromBitmap(System.Drawing.Bitmap bmp)
    {
        var img = new Img(bmp.Width, bmp.Height);
        var r = new System.Drawing.Rectangle(0, 0, bmp.Width, bmp.Height);
        var d = bmp.LockBits(r, System.Drawing.Imaging.ImageLockMode.ReadOnly, System.Drawing.Imaging.PixelFormat.Format24bppRgb);
        try
        {
            var row = new byte[d.Stride];
            for (int y = 0; y < img.H; y++)
            {
                System.Runtime.InteropServices.Marshal.Copy(d.Scan0 + y * d.Stride, row, 0, d.Stride);
                for (int x = 0; x < img.W; x++)
                {
                    int o = (y * img.W + x) * 3;
                    img.P[o] = row[x * 3 + 2]; img.P[o + 1] = row[x * 3 + 1]; img.P[o + 2] = row[x * 3];
                }
            }
        }
        finally { bmp.UnlockBits(d); }
        return img;
    }

    // Resize a captured bitmap to the reference size (no-op when it already is).
    public static Img FromBitmapResized(System.Drawing.Bitmap bmp, int w, int h)
    {
        if (bmp.Width == w && bmp.Height == h) return FromBitmap(bmp);
        using (var dst = new System.Drawing.Bitmap(w, h, System.Drawing.Imaging.PixelFormat.Format24bppRgb))
        {
            using (var g = System.Drawing.Graphics.FromImage(dst))
            {
                g.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.HighQualityBilinear;
                g.PixelOffsetMode = System.Drawing.Drawing2D.PixelOffsetMode.Half;
                g.DrawImage(bmp, new System.Drawing.Rectangle(0, 0, w, h));
            }
            return FromBitmap(dst);
        }
    }
}

// The four rectangles copied from the screen, on the 2560 x 1440 reference.
public static class Regions
{
    public const int RefW = 2560, RefH = 1440;
    public static readonly System.Drawing.Rectangle XpLine = new System.Drawing.Rectangle(560, 305, 320, 23);     // character screen: "... of 128,782,495"
    public static readonly System.Drawing.Rectangle NewStats = new System.Drawing.Rectangle(580, 1055, 81, 80);   // left level-up button
    public static readonly System.Drawing.Rectangle NewSkill = new System.Drawing.Rectangle(1888, 1055, 81, 80);  // right level-up button
    public static readonly System.Drawing.Rectangle Hud = new System.Drawing.Rectangle(766, 1306, 1033, 38);      // XP bar and its frame
    public static System.Drawing.Rectangle[] All { get { return new[] { XpLine, NewStats, NewSkill, Hud }; } }
}

public sealed class Reading
{
    public bool Hud;            // the HUD frame is on screen, whole
    public double Xp;           // 0..1, progress inside the level (valid when Hud)
    public bool NewStats, NewSkill;
    public int PanelLevel = -1; // level read from the character screen; -1 = closed or unreadable
    public long PanelNumber;    // the number read there (experience for the next level)
    public double HudScore, StatsScore, SkillScore;

    public override string ToString()
    {
        var c = System.Globalization.CultureInfo.InvariantCulture;
        return "hud=" + (Hud ? "yes" : "no") + " (" + HudScore.ToString("0.00", c) + ")"
            + (Hud ? " xp=" + Xp.ToString("0.000", c) : "")
            + " stats=" + StatsScore.ToString("0.00", c) + (NewStats ? "*" : "")
            + " skill=" + SkillScore.ToString("0.00", c) + (NewSkill ? "*" : "")
            + (PanelLevel > 0 ? " panel=level " + PanelLevel + " (" + PanelNumber + ")" : "");
    }
}

public static class Reader
{
    public const double HudMin = 0.80, IconMin = 0.80;

    // At 2560 x 1440 the digits are the templates themselves. At other resolutions the game draws
    // them at another size (9 px tall at 1080p) and the resized capture only resembles the
    // templates (IoU 0.6-0.75 measured at 1080p), so the text threshold and the minimum
    // likeness go down. A misread digit still cannot pass: the whole number must be one of the
    // 98 values of the experience table.
    static bool Native(double scale) { return System.Math.Abs(scale - 1) < 0.01; }
    public static int InkFor(double scale) { return Native(scale) ? 185 : 150; }
    public static double DigitMinFor(double scale) { return Native(scale) ? 0.60 : 0.45; }

    // positions inside the regions (reference pixels)
    const int HudX0 = 770 - 766, HudX1 = 1794 - 766;                          // frame columns compared
    static readonly int[] HudRows = { 4, 5, 6, 7, 8, 9, 10, 32, 33, 34, 35 };   // y 1310..1316 and 1338..1341
    const int XpY = 1327 - 1306, XpX0 = 776 - 766, XpX1 = 1793 - 766;           // middle line of the XP bar
    const int IconX = 5, IconY = 5, IconW = 71, IconH = 70;                     // icon at 585,1060 inside 580,1055
    const int LineY0 = 311 - 305, LineH = 12, LineRight = 870 - 560;            // XP line glyph rows and where to start

    static readonly int HudW = HudX1 - HudX0 + 1;
    static readonly byte[] T_HUD = System.Convert.FromBase64String("%HUD_FRAME%");          // gray, HudRows.Length x HudW
    static readonly byte[] T_STATS = System.Convert.FromBase64String("%ICON_NEW_STATS%");   // gray, IconH x IconW
    static readonly byte[] T_SKILL = System.Convert.FromBase64String("%ICON_NEW_SKILL%");
    static readonly byte[] T_DIGITS = System.Convert.FromBase64String("%DIGITS%");          // binary, column by column
    static readonly int[] DigitW = { %DIGIT_WIDTHS% };

    // Images are the four regions, already at reference size; scale = game height / 1440.
    public static Reading Read(Img xpLine, Img stats, Img skill, Img hud, double scale)
    {
        var r = new Reading();
        r.HudScore = HudFrame(hud);
        r.Hud = r.HudScore >= HudMin;
        if (r.Hud) r.Xp = XpFill(hud);
        r.StatsScore = Icon(stats, T_STATS);
        r.SkillScore = Icon(skill, T_SKILL);
        r.NewStats = r.StatsScore >= IconMin;
        r.NewSkill = r.SkillScore >= IconMin;
        r.PanelNumber = PanelNumber(xpLine, InkFor(scale), DigitMinFor(scale));
        r.PanelLevel = XpTable.LevelShowing(r.PanelNumber);
        return r;
    }

    static double Ncc(int[] a, byte[] b)
    {
        double ma = 0, mb = 0; int n = a.Length;
        for (int i = 0; i < n; i++) { ma += a[i]; mb += b[i]; }
        ma /= n; mb /= n;
        double sab = 0, saa = 0, sbb = 0;
        for (int i = 0; i < n; i++) { double da = a[i] - ma, db = b[i] - mb; sab += da * db; saa += da * da; sbb += db * db; }
        return saa < 1e-6 || sbb < 1e-6 ? 0 : sab / System.Math.Sqrt(saa * sbb);
    }

    public static double HudFrame(Img q)
    {
        var a = new int[HudRows.Length * HudW];
        for (int j = 0; j < HudRows.Length; j++)
            for (int i = 0; i < HudW; i++)
                a[j * HudW + i] = q.Gray(HudX0 + i, HudRows[j]);
        return Ncc(a, T_HUD);
    }

    // where the white of the bar ends (last run of 3+ white columns), 0..1
    public static double XpFill(Img q)
    {
        int end = -1, run = 0;
        for (int x = XpX0; x <= XpX1; x++)
        {
            int votes = 0;
            for (int y = XpY - 1; y <= XpY + 1; y++) if (q.White(x, y)) votes++;
            if (votes >= 2) { run++; if (run >= 3) end = x; } else run = 0;
        }
        return end < 0 ? 0 : System.Math.Min(1.0, (end - XpX0 + 1) / (double)(XpX1 - XpX0 + 1));
    }

    // best match of the button picture within +-3 px
    public static double Icon(Img q, byte[] t)
    {
        double best = -1;
        var a = new int[IconW * IconH];
        for (int dy = -3; dy <= 3; dy++)
            for (int dx = -3; dx <= 3; dx++)
            {
                for (int j = 0; j < IconH; j++)
                    for (int i = 0; i < IconW; i++)
                        a[j * IconW + i] = q.Gray(IconX + i + dx, IconY + j + dy);
                double s = Ncc(a, t);
                if (s > best) best = s;
            }
        return best;
    }

    // The right-aligned number of the XP line, read from the right until the space before it.
    // Separators (comma, dot, space) are skipped, so it does not matter how the language writes
    // thousands. Returns 0 when there is no believable number.
    public static long PanelNumber(Img q, int ink, double digitMin)
    {
        // the 12 text rows: where the ink is, within 3 px of the 1440p position (at 1080p the
        // resized text lands one row lower)
        var rows = new int[q.H];
        for (int y = 0; y < q.H; y++)
            for (int x = 0; x < q.W; x++) if (q.Gray(x, y) > ink) rows[y]++;
        int y0 = LineY0, bestInk = -1;
        for (int y = System.Math.Max(0, LineY0 - 3); y <= System.Math.Min(q.H - LineH, LineY0 + 3); y++)
        {
            int sum = 0;
            for (int k = 0; k < LineH; k++) sum += rows[y + k];
            if (sum > bestInk) { bestInk = sum; y0 = y; }
        }
        var col = new int[q.W];
        for (int x = 0; x < q.W; x++)
            for (int y = y0; y < y0 + LineH; y++)
                if (q.Gray(x, y) > ink) col[x]++;
        var glyphs = new System.Collections.Generic.List<int[]>();   // [x0, x1], right to left
        int end = -1, gap = 0;
        for (int x = System.Math.Min(LineRight, q.W - 1); x >= 0; x--)
        {
            if (col[x] > 0) { if (end < 0) end = x; gap = 0; continue; }
            if (end >= 0) { glyphs.Add(new[] { x + 1, end }); end = -1; }
            if (glyphs.Count > 0 && ++gap >= 8) break;
        }
        if (end >= 0) return 0;                       // ran into the region's left edge
        if (glyphs.Count == 0) return 0;
        long n = 0; int digits = 0;
        for (int k = glyphs.Count - 1; k >= 0; k--)
        {
            int x0 = glyphs[k][0], x1 = glyphs[k][1];
            bool top = false;                          // separators have no ink in the upper half
            for (int x = x0; x <= x1 && !top; x++)
                for (int y = y0; y < y0 + 7; y++) if (q.Gray(x, y) > ink) { top = true; break; }
            if (!top) continue;
            int d = Digit(q, x0, x1, y0, ink, digitMin);
            if (d < 0) return 0;
            n = n * 10 + d;
            if (++digits > 10) return 0;
        }
        return digits >= 3 ? n : 0;
    }

    // IoU of the glyph's ink with each digit template, aligned on the left (+-1 px)
    static int Digit(Img q, int x0, int x1, int y0, int ink, double digitMin)
    {
        int best = -1; double score = 0; int off = 0;
        for (int d = 0; d < 10; d++)
        {
            int w = DigitW[d];
            for (int dx = -1; dx <= 1; dx++)
            {
                int inter = 0, union = 0;
                int a = System.Math.Min(x0, x0 + dx), b = System.Math.Max(x1, x0 + dx + w - 1);
                for (int x = a; x <= b; x++)
                    for (int j = 0; j < LineH; j++)
                    {
                        bool g = x >= x0 && x <= x1 && q.Gray(x, y0 + j) > ink;
                        int i = x - (x0 + dx);
                        bool t = i >= 0 && i < w && T_DIGITS[off + i * LineH + j] != 0;
                        if (g && t) inter++;
                        if (g || t) union++;
                    }
                double s = union == 0 ? 0 : inter / (double)union;
                if (s > score) { score = s; best = d; }
            }
            off += w * LineH;
        }
        return score >= digitMin ? best : -1;
    }
}

// Diablo II experience table (cumulative experience to reach each level; the same in D2R).
public static class XpTable
{
    public static readonly long[] Exp = {
        0, 0, 500, 1500, 3750, 7875, 14175, 22680, 32886, 44396, 57715, 72144, 90180, 112725, 140906, 176132, 220165,
        275207, 344008, 430010, 537513, 671891, 839864, 1049830, 1312287, 1640359, 2050449, 2563061, 3203826, 3902260,
        4663553, 5493363, 6397855, 7383752, 8458379, 9629723, 10906488, 12298162, 13815086, 15468534, 17270791,
        19235252, 21376515, 23710491, 26254525, 29027522, 32050088, 35344686, 38935798, 42850109, 47116709, 51767302,
        56836449, 62361819, 68384473, 74949165, 82104680, 89904191, 98405658, 107672256, 117772849, 128782495,
        140783010, 153863570, 168121381, 183662396, 200602101, 219066380, 239192444, 261129853, 285041630, 311105466,
        339515048, 370481492, 404234916, 441026148, 481128591, 524840254, 572485967, 624419793, 681027665, 742730244,
        809986056, 883294891, 963201521, 1050299747, 1145236814, 1248718217, 1361512946, 1484459201, 1618470619,
        1764543065, 1923762030, 2097310703, 2286478756, 2492671933, 2717422497, 2962400612, 3229426756, 3520485254 };

    // The character screen of a level L character shows "... of Exp[L + 1]". -1 when the
    // number is not in the table (not the character screen, or a misread).
    public static int LevelShowing(long nextLevelExp)
    {
        if (nextLevelExp <= 0) return -1;
        for (int l = 2; l < Exp.Length; l++) if (Exp[l] == nextLevelExp) return l - 1;
        return -1;
    }
}

// Turns readings into events, tick by tick.
//   level up = the XP bar drops by DropMin or more and is still down on the next tick (no hole
//   in the HUD longer than 3 s), AND there is a sign: a level-up button now or on the tick
//   before, or the character screen open (it hides the left button; with the skill tree open
//   too, no button is left on screen). With the character screen open, its level is used.
//   The buttons alone never count: they come back when a panel closes and when entering a game
//   with unspent points. The character screen otherwise only corrects; showing exactly +1 up to
//   60 s after a drop that had no sign counts as a (late) level up.
//   Level 98 and 99 show the same number (the top of the table, 3,520,485,254): a 99 is never
//   "corrected" to 98, and a level up from 98 with the character screen open gives 99.
public sealed class Tracker
{
    public const double DropMin = 0.30;
    public int Level = -1;
    public double Xp = -1;
    double prevXp = -1, dropFrom = -1;
    bool prevButton;
    System.DateTime noHudSince = System.DateTime.MinValue, lastUp = System.DateTime.MinValue, unsignedDrop = System.DateTime.MinValue;

    static string F(double v) { return v.ToString("0.00", System.Globalization.CultureInfo.InvariantCulture); }

    // returns "up", "corrected" or null; why = a line for the log
    public string Step(Reading r, System.DateTime now, out string why)
    {
        why = null;
        string ev = null;
        bool panel = r.PanelLevel > 0;
        if (!r.Hud)
        {
            if (noHudSince == System.DateTime.MinValue) noHudSince = now;
            if ((now - noHudSince).TotalSeconds > 15) { prevXp = -1; dropFrom = -1; }   // left the game: forget the bar
            prevButton = false;
            return Correct(r, now, ref why);
        }
        bool hole = noHudSince != System.DateTime.MinValue && (now - noHudSince).TotalSeconds > 3;
        noHudSince = System.DateTime.MinValue;
        bool button = r.NewStats || r.NewSkill;
        bool sign = button || prevButton || panel;
        if (hole) dropFrom = -1;
        else if (dropFrom >= 0)
        {
            if (r.Xp <= dropFrom - DropMin)
            {
                string how = "bar " + F(dropFrom) + " -> " + F(r.Xp) + ", "
                    + (r.NewStats && r.NewSkill ? "both buttons" : r.NewStats ? "New Stats button" : r.NewSkill ? "New Skill button"
                       : prevButton ? "button on the tick before" : "character screen open");
                if (!sign) { why = "bar dropped " + F(dropFrom) + " -> " + F(r.Xp) + " with no button and no character screen: not counted"; unsignedDrop = now; }
                else if ((now - lastUp).TotalSeconds <= 20) why = how + ": ignored (leveled up less than 20 s ago)";
                else if (panel || Level > 0)
                {
                    bool top = r.PanelNumber == XpTable.Exp[99];       // 98 or 99: the screen cannot tell
                    Level = panel && !(top && Level == 98) ? r.PanelLevel : System.Math.Min(99, Level + 1);
                    lastUp = now;
                    why = how;
                    ev = "up";
                }
                else why = how + ": leveled up, but the level is not known yet (open the character screen or use the command)";
            }
            dropFrom = -1;
        }
        else if (prevXp >= 0 && r.Xp <= prevXp - DropMin) dropFrom = prevXp;   // confirm on the next tick
        if (dropFrom < 0) prevXp = r.Xp;
        Xp = r.Xp;
        prevButton = button;
        if (ev == null && dropFrom < 0) ev = Correct(r, now, ref why);
        return ev;
    }

    string Correct(Reading r, System.DateTime now, ref string why)
    {
        int screen = r.PanelLevel;
        if (screen == 98 && r.PanelNumber == XpTable.Exp[99] && Level == 99) screen = 99;   // same number at 98 and 99
        if (screen <= 0 || screen == Level) return null;
        bool late = Level > 0 && screen == Level + 1 && (now - unsignedDrop).TotalSeconds < 60;
        why = "character screen: level " + screen + (Level > 0 ? " (was " + Level + ")" : "") + (late ? ", after the bar dropped" : "");
        Level = screen;
        if (!late) return "corrected";
        lastUp = now;
        unsignedDrop = System.DateTime.MinValue;
        return "up";
    }
}
