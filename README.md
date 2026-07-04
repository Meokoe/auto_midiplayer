# MIDI autoplayer

Import MIDI files, map notes to 21 keys for in-game instruments, auto-play via background key simulation.

## Features

- **MIDI Import & Playback** — Import .mid files, auto-map to 21-key keyboard
- **Playlist** — Track management (import/delete/notes), persistent storage
- **Dual Key Modes** — Mode 1 (1-7 / Q-U / A-J) | Mode 2 (Q-U / A-J / Z-M)
- **Black Key Strategy** — Snap to nearest white key or Skip
- **Octave Shift** — -2..+2 shift the 21-note window
- **Global Hotkeys** — pynput background listener, works even when game window is focused
- **Visualization** — 21-key real-time highlight + Note density timeline chart + Stats panel

## Hotkeys

| Action | Default |
|--------|---------|
| Play/Pause | `Ctrl+Alt+P` |
| Stop | `Ctrl+Alt+S` |
| Forward 5s | `Ctrl+Alt+→` |
| Backward 5s | `Ctrl+Alt+←` |
| Speed Up | `Ctrl+Alt+↑` |
| Speed Down | `Ctrl+Alt+↓` |

Customize in Settings window (gear icon).

## Run

```bash
python main.py
# or
e:/anacondaaaa/python.exe main.py
```

## Build EXE

```bash
build_exe.bat
# Output: dist/MIDI自动演奏.exe
```

## Project Structure

```
main.py                 Entry point
core/
  keymap.py             Two key-mode layouts
  midi_loader.py        MIDI parsing -> event list
  note_mapper.py        Note -> 0..20 key index
  key_player.py         Threaded scheduler + pynput key simulation
  settings.py           JSON config read/write
ui/
  player_window.py      Main window (dark DAW-style)
  playlist_panel.py     Playlist panel
  settings_window.py    Hotkey settings dialog
  hotkey_listener.py    Global hotkey listener
build_exe.bat           One-click EXE build script
```
