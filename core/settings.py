"""配置持久化: 快捷键绑定 + 播放列表条目, JSON 文件存到 %APPDATA%/midi_player/settings.json"""

from __future__ import annotations

import json
import os
import sys

APP_NAME = "midi_player"

DEFAULTS = {
    "hotkeys": {
        "play_pause":  "<ctrl>+<alt>+p",
        "stop":        "<ctrl>+<alt>+s",
        "forward":     "<ctrl>+<alt>+<right>",
        "backward":    "<ctrl>+<alt>+<left>",
        "speed_up":    "<ctrl>+<alt>+<up>",
        "speed_down":  "<ctrl>+<alt>+<down>",
    },
    "playlist": [],  # [{"path": str, "note": str, "duration_s": float}, ...]
}


def _settings_path() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~/.config")
    folder = os.path.join(base, APP_NAME)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "settings.json")


def load() -> dict:
    path = _settings_path()
    if not os.path.exists(path):
        return dict(DEFAULTS)  # shallow copy
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return dict(DEFAULTS)

    # 合并缺失 key, 防止旧格式崩溃
    for section, defaults in DEFAULTS.items():
        if section not in data:
            data[section] = defaults
        elif isinstance(defaults, dict):
            for k, v in defaults.items():
                if k not in data[section]:
                    data[section][k] = v
    return data


def save(data: dict):
    path = _settings_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def update_playlist(playlist: list):
    data = load()
    data["playlist"] = playlist
    save(data)


def update_hotkeys(hotkeys: dict):
    data = load()
    data["hotkeys"] = hotkeys
    save(data)
