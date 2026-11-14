// D2R Level Overlay — options shared by the overlay (index.html) and the configurator
// (configure.html). Every option is a URL parameter of index.html; anything left out uses
// the preset's value, and the preset's missing values come from DEFAULTS.
(function () {
  const LANGS = {
    "en":    { name: "English",    level: "Level",     xp: "Experience",  up: "Level up!",            next: "to {n}" },
    "pt-BR": { name: "Português",  level: "Nível",     xp: "Experiência", up: "Subiu de nível!",      next: "para o {n}" },
    "es":    { name: "Español",    level: "Nivel",     xp: "Experiencia", up: "¡Subiste de nivel!",   next: "para el {n}" },
    "fr":    { name: "Français",   level: "Niveau",    xp: "Expérience",  up: "Niveau supérieur !",   next: "vers le {n}" },
    "de":    { name: "Deutsch",    level: "Stufe",     xp: "Erfahrung",   up: "Stufenaufstieg!",      next: "bis {n}" },
    "it":    { name: "Italiano",   level: "Livello",   xp: "Esperienza",  up: "Livello superiore!",   next: "verso il {n}" },
    "pl":    { name: "Polski",     level: "Poziom",    xp: "Doświadczenie", up: "Nowy poziom!",       next: "do {n}" },
    "ru":    { name: "Русский",    level: "Уровень",   xp: "Опыт",        up: "Новый уровень!",       next: "до {n}" },
  };

  // Fonts offered by the configurator (all from Google Fonts; any other Google Font name works too).
  const FONTS = ["Cinzel", "Cinzel Decorative", "Grenze Gotisch", "MedievalSharp", "Pirata One", "UnifrakturCook",
    "Barlow Semi Condensed", "Oswald", "Bebas Neue", "Rajdhani", "Teko", "Inter", "Roboto Condensed", "Montserrat",
    "Exo 2", "Orbitron", "Press Start 2P", "Silkscreen"];

  const DEFAULTS = {
    lang: "en", layout: "classic", bar: "segments", align: "left",
    accent: "bfa468", text: "efe6d2", number: "f3ead6", fill1: "fff3c4", fill2: "8a7038", track: "0b0b0c", glow: "ffd678",
    fontLabel: "Cinzel", fontNumber: "Grenze Gotisch", fontText: "Barlow Semi Condensed",
    panel: "0", panelColor: "141416", panelAlpha: "0.85", radius: "4",
    pct: "1", next: "0", icon: "1", shadow: "1", anim: "1", hide: "1",
    labelLevel: "", labelXp: "", labelUp: "",
    host: "127.0.0.1", port: "8080", pass: "", action: "D2R Level", event: "d2r_level",
  };

  const PRESETS = {
    sanctuary: { title: "Sanctuary (gold)" },
    blood:     { title: "Blood", accent: "c2373f", text: "f1dede", number: "ffffff", fill1: "ff8a8a", fill2: "7a0d16", glow: "ff4a4a",
                 fontLabel: "Cinzel", fontNumber: "Pirata One" },
    frost:     { title: "Frost", accent: "8fc7ff", text: "e6f2ff", number: "ffffff", fill1: "e9f6ff", fill2: "2a6fb3", glow: "8fd0ff",
                 fontLabel: "Cinzel", fontNumber: "Cinzel" },
    clean:     { title: "Clean", accent: "ffffff", text: "ffffff", number: "ffffff", fill1: "ffffff", fill2: "b8b8b8", track: "000000",
                 glow: "ffffff", fontLabel: "Inter", fontNumber: "Inter", fontText: "Inter", panel: "1", panelColor: "000000", panelAlpha: "0.55", radius: "10" },
    neon:      { title: "Neon", accent: "00e5ff", text: "e8fbff", number: "ffffff", fill1: "00e5ff", fill2: "b400ff", track: "05010a",
                 glow: "00e5ff", fontLabel: "Orbitron", fontNumber: "Orbitron", fontText: "Rajdhani", bar: "solid" },
    pixel:     { title: "Pixel", accent: "f5d76e", text: "ffffff", number: "ffffff", fill1: "f5d76e", fill2: "c08a1e", track: "1a1a1a",
                 glow: "f5d76e", fontLabel: "Press Start 2P", fontNumber: "Press Start 2P", fontText: "Silkscreen", bar: "segments" },
  };

  const LAYOUTS = {
    classic:   { title: "Classic (icon, level, XP bar)", w: 664, h: 104 },
    stacked:   { title: "Stacked (level over the bar)", w: 664, h: 104 },
    medallion: { title: "Medallion (ring = XP)", w: 420, h: 104 },
    minimal:   { title: "Minimal (just the level)", w: 260, h: 104 },
  };

  // URLSearchParams -> full option object (preset, then explicit parameters)
  function options(params) {
    const p = Object.assign({}, DEFAULTS, PRESETS[params.get("preset")] || {});
    for (const k of Object.keys(DEFAULTS)) if (params.has(k)) p[k] = params.get(k);
    p.preset = params.get("preset") || "sanctuary";
    if (!LANGS[p.lang]) p.lang = "en";
    if (!LAYOUTS[p.layout]) p.layout = "classic";
    delete p.title;
    return p;
  }

  // option object -> query string with only what differs from the preset
  function query(o) {
    const base = Object.assign({}, DEFAULTS, PRESETS[o.preset] || {});
    const q = new URLSearchParams();
    if (o.preset && o.preset !== "sanctuary") q.set("preset", o.preset);
    for (const k of Object.keys(DEFAULTS)) if (o[k] !== undefined && String(o[k]) !== String(base[k])) q.set(k, o[k]);
    return q.toString();
  }

  window.D2RL = { LANGS, FONTS, DEFAULTS, PRESETS, LAYOUTS, options, query };
})();
