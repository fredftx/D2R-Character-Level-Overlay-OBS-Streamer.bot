// D2R Level Overlay — the Streamer.bot action ("D2R Level").
//
// Every second, only while Diablo II: Resurrected is the foreground window, it copies one
// rectangle of the SCREEN (like Print Screen / OBS display capture), reads four small areas of it
// (Reader.cs) and broadcasts {"d2r_level": {...}} on Streamer.bot's WebSocket server for
// overlay/index.html.
//
// What it uses from Windows, and nothing else (build.py refuses to package anything more):
//   GetForegroundWindow, GetWindowThreadProcessId  - is the window in front the game's?
//   GetClientRect, ClientToScreen                  - where and how big is the game on screen?
//   SetThreadDpiAwarenessContext                   - real pixels on scaled displays (this thread only)
//   Graphics.CopyFromScreen                        - copy pixels of the desktop
//   Process.GetProcessesByName("D2R")              - process ids from the system's process list
// It never opens the game process, never reads or writes its memory, never injects anything,
// never sends keys or clicks, never touches the game's files.

public class CPHInline
{
    // ---- settings ---------------------------------------------------------------------------
    const string EVENT = "d2r_level";          // WebSocket broadcast the overlay listens to
    const string GLOBAL_LEVEL = "d2r_level";   // persisted global variable with the level
    const string GLOBAL_STATE = "d2r_level_state";
    const string PROCESS = "D2R";              // D2R.exe
    const int TICK_MS = 1000;
    // ------------------------------------------------------------------------------------------

    System.Threading.Timer timer;
    int busy;
    readonly object gate = new object();
    readonly Tracker tracker = new Tracker();
    bool running, runningKnown;
    System.DateTime lastProcessCheck = System.DateTime.MinValue, lastError = System.DateTime.MinValue;
    string lastSent = "", lastWarning = "", lastState = "";

    [System.Runtime.InteropServices.DllImport("user32.dll")] static extern System.IntPtr GetForegroundWindow();
    [System.Runtime.InteropServices.DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(System.IntPtr hWnd, out uint processId);
    [System.Runtime.InteropServices.DllImport("user32.dll")] static extern bool GetClientRect(System.IntPtr hWnd, out RECT rect);
    [System.Runtime.InteropServices.DllImport("user32.dll")] static extern bool ClientToScreen(System.IntPtr hWnd, ref POINT point);
    [System.Runtime.InteropServices.DllImport("user32.dll")] static extern System.IntPtr SetThreadDpiAwarenessContext(System.IntPtr context);
    struct RECT { public int Left, Top, Right, Bottom; }
    struct POINT { public int X, Y; }

    public void Init() { Start(); }

    public void Dispose()
    {
        if (timer != null) { timer.Dispose(); timer = null; }
    }

    void Start()
    {
        if (timer == null) timer = new System.Threading.Timer(delegate { Tick(); }, null, 3000, TICK_MS);
    }

    // Runs on "Streamer.bot Started", when the overlay asks for the current state, and on the
    // chat command (!level N / !level + / !level -, broadcaster and moderators).
    public bool Execute()
    {
        Start();
        string command;
        if (CPH.TryGetArg("command", out command) && !string.IsNullOrEmpty(command)) return Command();
        lock (gate) { LoadLevel(); Send(false, true); }
        return true;
    }

    void LoadLevel()
    {
        int n = CPH.GetGlobalVar<int>(GLOBAL_LEVEL, true);
        if (n >= 1 && n <= 99) tracker.Level = n;
    }

    void SaveLevel() { if (tracker.Level > 0) CPH.SetGlobalVar(GLOBAL_LEVEL, tracker.Level, true); }

    bool Command()
    {
        bool allowed = Flag("isBroadcaster") || Flag("isModerator");
        object role;
        int r;
        if (CPH.TryGetArg("role", out role) && role != null && int.TryParse(role.ToString(), out r) && r >= 3) allowed = true;
        string input;
        CPH.TryGetArg("rawInput", out input);
        input = (input ?? "").Trim();
        if (!allowed || input == "") return true;
        lock (gate)
        {
            LoadLevel();
            int n;
            if (input == "+") n = tracker.Level + 1;
            else if (input == "-") n = tracker.Level - 1;
            else if (!int.TryParse(input, out n)) return true;
            if (n < 1 || n > 99) return true;
            tracker.Level = n;
            SaveLevel();
            CPH.LogInfo("[D2R Level] set by command: level " + n);
            Send(false, true);
        }
        return true;
    }

    bool Flag(string name)
    {
        object o;
        bool b;
        return CPH.TryGetArg(name, out o) && o != null && bool.TryParse(o.ToString(), out b) && b;
    }

    void Tick()
    {
        if (System.Threading.Interlocked.Exchange(ref busy, 1) == 1) return;
        try { lock (gate) Step(); }
        catch (System.Exception e)
        {
            if (System.DateTime.Now - lastError > System.TimeSpan.FromMinutes(10)) { CPH.LogWarn("[D2R Level] error: " + e.Message); lastError = System.DateTime.Now; }
        }
        finally { System.Threading.Interlocked.Exchange(ref busy, 0); }
    }

    static System.Collections.Generic.HashSet<uint> GamePids()
    {
        var ids = new System.Collections.Generic.HashSet<uint>();
        foreach (var p in System.Diagnostics.Process.GetProcessesByName(PROCESS)) { ids.Add((uint)p.Id); p.Dispose(); }
        return ids;
    }

    void Step()
    {
        var now = System.DateTime.Now;
        var pids = (now - lastProcessCheck).TotalSeconds >= 10 || running ? GamePids() : null;
        if (pids != null && (now - lastProcessCheck).TotalSeconds >= 10)
        {
            lastProcessCheck = now;
            bool r = pids.Count > 0;
            if (!runningKnown || r != running)
            {
                running = r; runningKnown = true;
                CPH.LogInfo("[D2R Level] " + (r ? "game running" : "game closed"));
                if (r) LoadLevel();
                Send(false, false);
            }
        }
        if (!running || pids == null) return;

        var h = GetForegroundWindow();
        uint pid;
        GetWindowThreadProcessId(h, out pid);
        if (!pids.Contains(pid)) return;                      // game not in front: nothing of it on screen

        Reading reading;
        var previous = SetThreadDpiAwarenessContext(new System.IntPtr(-4));   // per-monitor v2
        try
        {
            RECT rc; GetClientRect(h, out rc);
            var origin = new POINT();
            ClientToScreen(h, ref origin);
            int w = rc.Right - rc.Left, ht = rc.Bottom - rc.Top;
            if (ht < 600 || System.Math.Abs(w / (double)ht - 16.0 / 9.0) > 0.02)
            {
                Warn("the game is " + w + "x" + ht + ": only 16:9 resolutions are supported for now");
                return;
            }
            Warn("");
            double s = ht / (double)Regions.RefH;
            double ox = origin.X + (w - Regions.RefW * s) / 2, oy = origin.Y;
            var imgs = CopyRegions(s, ox, oy);
            reading = Reader.Read(imgs[0], imgs[1], imgs[2], imgs[3], s);
        }
        finally { if (previous != System.IntPtr.Zero) SetThreadDpiAwarenessContext(previous); }

        LoadLevel();
        string why;
        string ev = tracker.Step(reading, now, out why);
        if (why != null) CPH.LogInfo("[D2R Level] " + (ev == "up" ? "LEVEL UP: " + tracker.Level + " - " : "") + why);
        if (ev != null) SaveLevel();
        State(reading);
        Send(ev == "up", false);
    }

    // Where a reference rectangle lands on the screen at this game size.
    static System.Drawing.Rectangle OnScreen(System.Drawing.Rectangle r, double s, double ox, double oy)
    {
        return new System.Drawing.Rectangle((int)System.Math.Round(ox + r.X * s), (int)System.Math.Round(oy + r.Y * s),
            System.Math.Max(1, (int)System.Math.Round(r.Width * s)), System.Math.Max(1, (int)System.Math.Round(r.Height * s)));
    }

    // ONE screen copy of the rectangle around the four regions, then cut and resize in memory:
    // each CopyFromScreen costs ~20 ms almost whatever its size (measured: 60x60 22 ms, the
    // whole 1920x1080 screen 41 ms), so one copy is much cheaper than four.
    static Img[] CopyRegions(double s, double ox, double oy)
    {
        var all = Regions.All;
        var spots = new System.Drawing.Rectangle[all.Length];
        var box = System.Drawing.Rectangle.Empty;
        for (int i = 0; i < all.Length; i++)
        {
            spots[i] = OnScreen(all[i], s, ox, oy);
            box = i == 0 ? spots[i] : System.Drawing.Rectangle.Union(box, spots[i]);
        }
        var imgs = new Img[all.Length];
        using (var bmp = new System.Drawing.Bitmap(box.Width, box.Height, System.Drawing.Imaging.PixelFormat.Format24bppRgb))
        {
            using (var g = System.Drawing.Graphics.FromImage(bmp))
                g.CopyFromScreen(box.X, box.Y, 0, 0, box.Size, System.Drawing.CopyPixelOperation.SourceCopy);
            for (int i = 0; i < all.Length; i++)
            {
                var part = new System.Drawing.Rectangle(spots[i].X - box.X, spots[i].Y - box.Y, spots[i].Width, spots[i].Height);
                using (var piece = bmp.Clone(part, System.Drawing.Imaging.PixelFormat.Format24bppRgb))
                    imgs[i] = Img.FromBitmapResized(piece, all[i].Width, all[i].Height);
            }
        }
        return imgs;
    }

    void Warn(string s)
    {
        if (s == lastWarning) return;
        lastWarning = s;
        if (s != "") CPH.LogWarn("[D2R Level] " + s);
    }

    // Variables > Globals: what the last tick saw (only when it changes)
    void State(Reading r)
    {
        string s = (r.Hud ? "hud, xp " + System.Math.Round(r.Xp, 2).ToString(System.Globalization.CultureInfo.InvariantCulture) : "no hud")
            + (r.NewStats ? ", New Stats button" : "") + (r.NewSkill ? ", New Skill button" : "")
            + (r.PanelLevel > 0 ? ", character screen: level " + r.PanelLevel : "");
        if (s == lastState) return;
        lastState = s;
        CPH.SetGlobalVar(GLOBAL_STATE, System.DateTime.Now.ToString("HH:mm:ss") + " " + s, false);
    }

    void Send(bool levelUp, bool always)
    {
        var c = System.Globalization.CultureInfo.InvariantCulture;
        string level = tracker.Level > 0 ? tracker.Level.ToString(c) : "null";
        string xp = tracker.Xp >= 0 ? System.Math.Round(tracker.Xp, 3).ToString("0.###", c) : "null";
        string body = "\"level\":" + level + ",\"xp\":" + xp + ",\"running\":" + (running || !runningKnown ? "true" : "false");
        if (!always && !levelUp && body == lastSent) return;
        lastSent = body;
        CPH.WebsocketBroadcastJson("{\"" + EVENT + "\":{" + body + ",\"levelUp\":" + (levelUp ? "true" : "false") + "}}");
    }
}
