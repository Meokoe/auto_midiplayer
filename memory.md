# MIDI自动演奏 — Project Summary

## Current State
All features verified and working. Final deliverable: `dist/MIDI自动演奏.exe` (13 MB, single-file, no console).

## Recent Changes (2026-07-01)

### Bug Fixes
1. **Note edit popup** — Replaced `CTkInputDialog` (broken in some versions) with custom `CTkToplevel` + `CTkEntry` dialog. Double-click the note area to edit.
2. **Keyboard visual reversed** — Fixed: top row now shows high octave keys (A-J for M1, Q-U for M2), middle=mid (Q-U / A-J), bottom=low (1-7 / Z-M). Labels "高/中/低" preserved.
3. **Keymap reordered** — `MODE_1 = [low=1-7, mid=Q-U, high=A-J]`; `MODE_2 = [low=Z-M, mid=A-J, high=Q-U]`. UI draws high(14..20) top, mid(7..13) middle, low(0..6) bottom.
4. **Mode labels corrected** — `MODE_1_LABEL = "模式1  高八度=A-J  中八度=Q-U  低八度=1-7"`; `MODE_2_LABEL = "模式2  高八度=Q-U  中八度=A-J  低八度=Z-M"`.
4. **Long filename overflow** — Filenames >22 chars now truncated with ellipsis so the delete (✕) button is always visible.

### Enhancements
5. **Track Info Panel** — Right-side panel replaces empty space: 3 stat cards (total notes, note range, density) + waveform timeline chart with playback position indicator.
6. **Wider layout** — Window expanded from 980×680 to 1100×700. Playlist panel widened from 260 to 300 px.
7. **Playlist note label** — Changed from "点击添加备注" to "双击此处添加备注" for clarity.
8. **build_exe.bat & README** — English labels for broader usability.

## How to Run

```bash
# Source run (needs Python + deps):
e:/anacondaaaa/python.exe main.py

# EXE run (no Python needed):
dist/MIDI自动演奏.exe

# Rebuild EXE:
build_exe.bat
```

## Verification
- Smoke test: ✅ (key mapping, playback scheduling)
- E2E test: ✅ (play/pause/seek/stop cycle)
- GUI construction: ✅ (customtkinter window + playlist + hotkey listener)
- EXE launch: ✅ (no import errors)
