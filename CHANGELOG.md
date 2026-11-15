# Changelog

What changed in each version. Download: [latest release](https://github.com/fredftx/D2R-Character-Level-Overlay-OBS-Streamer.bot/releases/latest).

## 1.0.0 — 2026-11-15

First public release.

**Reader** (the Streamer.bot action)
- Level and XP progress read from the screen once per second, only while Diablo II: Resurrected is the window in front. One screen copy per second, about 35 ms of one CPU core at 1920 × 1080.
- Works with any game language: it matches the game's own interface (HUD XP bar and frame, the "New Stats" / "New Skill" buttons) and reads the next-level number of the character screen, looked up in the experience table.
- Any 16:9 resolution on any monitor, DPI-aware. Tested in real play at 2560 × 1440 and 1920 × 1080.
- Level ups: an XP drop confirmed on the next second, plus a level-up button or the character screen. The character screen corrects the level whenever it is open, and levels 98 and 99 are told apart.
- `!level` chat command: `!level 62`, `!level +`, `!level -` (broadcaster and moderators, Twitch).
- Safety check in `build.py`: the package is not built if the code uses any Windows call outside the five it needs.

**Overlay**
- 5 layouts (classic, stacked, medallion, orb, minimal) and 12 presets, 6 of them with the Diablo II look and the game's own textures.
- Labels in 8 languages or your own words, any Google Font, your colors.
- Fits any browser-source size; can hide while the game is closed.
- Configurator with live preview and a level-up test, which gives the address to paste into OBS.

**Tools**: `record_samples.py` (screen samples to support new setups), `make_textures.py` (the textures from your own screenshots), `make_release.py` (the release zip).
