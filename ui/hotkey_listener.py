"""全局热键监听: pynput 后台线程, 修饰键+普通键组合匹配注册的 handler。"""

from __future__ import annotations

import threading
import time
from pynput.keyboard import Listener, Key, KeyCode


# 修饰键标准化映射
_MOD_MAP = {
    Key.ctrl_l: "ctrl",
    Key.ctrl_r: "ctrl",
    Key.alt_l: "alt",
    Key.alt_r: "alt",
    Key.alt_gr: "alt",
    Key.shift_l: "shift",
    Key.shift_r: "shift",
    Key.cmd_l: "cmd",
    Key.cmd_r: "cmd",
}

# 特殊键可读名
_KEY_NAME = {
    "up": "up", "down": "down", "left": "left", "right": "right",
    "space": "space", "tab": "tab", "enter": "enter", "esc": "esc",
    "backspace": "backspace", "delete": "delete",
    "home": "home", "end": "end", "page_up": "page_up", "page_down": "page_down",
}


class HotkeyListener:
    def __init__(self):
        self._handler_map: dict[str, callable] = {}
        self._pressed_mods: set = set()       # {'ctrl','alt','shift'}
        self._suppress_next = False           # 屏蔽应用程序自己的按键(播放时 Controller 触发的)
        self._lock = threading.Lock()
        self._listener: Listener | None = None
        self._running = False

    # ---- public ----
    def start(self, handler_map: dict[str, callable]):
        """handler_map: {'<ctrl>+<alt>+p': callback, ...}"""
        with self._lock:
            self._handler_map = dict(handler_map)
        if self._listener is None:
            self._listener = Listener(on_press=self._on_press, on_release=self._on_release)
            self._listener.start()
            self._running = True

    def stop(self):
        if self._listener:
            self._listener.stop()
            self._listener = None
            self._running = False

    def reload(self, handler_map: dict[str, callable]):
        with self._lock:
            self._handler_map = dict(handler_map)

    def ignore_current_event(self):
        """播放器在 emit 按键时调用此方法, 让 listener 忽略本次按键(不触发快捷键)。"""
        self._suppress_next = True

    # ---- internal ----
    def _on_press(self, key):
        # 屏蔽
        if self._suppress_next:
            self._suppress_next = False
            return

        name = self._key_name(key)
        is_mod = name in ("ctrl", "alt", "shift", "cmd")
        if is_mod:
            self._pressed_mods.add(name)
            return

        # 普通键按下 —— 构建组合字符串
        combo = self._build_combo(name)
        if combo is None:
            return

        handler = None
        with self._lock:
            handler = self._handler_map.get(combo)
        if handler:
            # 在新线程中执行避免阻塞 listener
            try:
                handler()
            except Exception:
                pass

    def _on_release(self, key):
        name = self._key_name(key)
        self._pressed_mods.discard(name)

    def _build_combo(self, normal_key: str) -> str | None:
        if not normal_key:
            return None
        parts = sorted(self._pressed_mods)  # alt,ctrl,shift 按字母序
        parts.append(normal_key)
        return "<" + ">+<".join(parts) + ">"

    @staticmethod
    def _key_name(key) -> str | None:
        if key in _MOD_MAP:
            return _MOD_MAP[key]
        if isinstance(key, Key):
            name = key.name
            if name in _KEY_NAME:
                return _KEY_NAME[name]
            if name and name.startswith("f") and len(name) <= 3:
                return name  # f1..f12
            return None  # 其他特殊键忽略
        if isinstance(key, KeyCode):
            ch = key.char
            if ch:
                return ch.lower()
        return None
