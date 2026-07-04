"""快捷键设置窗口: CTkToplevel 弹窗, 每行展示功能+当前热键+修改按钮。"""

from __future__ import annotations

import customtkinter as ctk
from pynput.keyboard import Listener, Key, KeyCode

from core import settings

# -------- helpers (same logic as hotkey_listener, but lightweight) --------
_MOD_MAP = {
    Key.ctrl_l: "ctrl", Key.ctrl_r: "ctrl",
    Key.alt_l: "alt", Key.alt_r: "alt", Key.alt_gr: "alt",
    Key.shift_l: "shift", Key.shift_r: "shift",
}
_KEY_NAME = {
    "up": "up", "down": "down", "left": "left", "right": "right",
    "space": "space", "tab": "tab", "enter": "enter", "esc": "esc",
    "backspace": "backspace", "delete": "delete",
    "home": "home", "end": "end", "page_up": "page_up", "page_down": "page_down",
}


def _combo_to_display(raw: str) -> str:
    # "<ctrl>+<alt>+p" → "Ctrl + Alt + P"
    parts = raw.strip("<>").split(">+<")
    return " + ".join(p.title() for p in parts)


def _key_label(key) -> str | None:
    if key in _MOD_MAP:
        return _MOD_MAP[key]
    if isinstance(key, Key):
        n = key.name
        if n in _KEY_NAME:
            return _KEY_NAME[n]
        if n and n.startswith("f") and len(n) <= 3:
            return n
        return None
    if isinstance(key, KeyCode) and key.char:
        return key.char.lower()
    return None


ACTIONS = [
    ("play_pause",  "播放 / 暂停"),
    ("stop",        "停止"),
    ("forward",     "快进 5秒"),
    ("backward",    "快退 5秒"),
    ("speed_up",    "加速"),
    ("speed_down",  "减速"),
]


class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, master, hotkeys: dict, on_save):
        super().__init__(master)
        self.title("快捷键设置")
        self.geometry("500x420")
        self.resizable(False, False)
        self.configure(fg_color="#1a1a1a")
        self.attributes("-topmost", True)

        self._hotkeys = dict(hotkeys)
        self._on_save = on_save   # callback(new_hotkeys)
        self._listening_for: str | None = None  # action_id 正在监听
        self._listener: Listener | None = None
        self._listening_label: ctk.CTkLabel | None = None
        self._listen_pressed_mods: set = set()

        self._build_ui()

    def _build_ui(self):
        ctk.CTkLabel(self, text="⚙  快捷键设置", font=("Microsoft YaHei", 18, "bold"),
                     text_color="#00d4ff").pack(pady=(16, 12))

        # header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=20)
        ctk.CTkLabel(hdr, text="功能", font=("Microsoft YaHei", 11, "bold"),
                     text_color="#888", width=120).pack(side="left")
        ctk.CTkLabel(hdr, text="快捷键", font=("Microsoft YaHei", 11, "bold"),
                     text_color="#888", width=160).pack(side="left", padx=10)
        ctk.CTkLabel(hdr, text="", width=100).pack(side="left")

        self._rows = {}
        for a_id, a_label in ACTIONS:
            self._add_row(a_id, a_label)

        # 监听提示
        self._listening_label = ctk.CTkLabel(self, text="", font=("Microsoft YaHei", 11),
                                             text_color="#ffab00")
        self._listening_label.pack(pady=(8, 4))

        # 底部按钮
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(pady=(8, 12))
        ctk.CTkButton(btns, text="恢复默认", width=100, height=34, corner_radius=8,
                      fg_color="#444", hover_color="#555", text_color="#e0e0e0",
                      font=("Microsoft YaHei", 12),
                      command=self._on_reset).pack(side="left", padx=8)
        ctk.CTkButton(btns, text="保存并关闭", width=120, height=34, corner_radius=8,
                      fg_color="#00e676", hover_color="#00ff7a", text_color="#000",
                      font=("Microsoft YaHei", 12, "bold"),
                      command=self._on_save_close).pack(side="left", padx=8)

    def _add_row(self, a_id: str, a_label: str):
        row = ctk.CTkFrame(self, fg_color="#252525", corner_radius=10)
        row.pack(fill="x", padx=20, pady=4)

        ctk.CTkLabel(row, text=a_label, font=("Microsoft YaHei", 13),
                     text_color="#e0e0e0", width=120,
                     anchor="w").pack(side="left", padx=14, pady=10)

        cur = self._hotkeys.get(a_id, "")
        self._key_labels = {}
        lbl = ctk.CTkLabel(row, text=_combo_to_display(cur), font=("Consolas", 12, "bold"),
                           text_color="#00d4ff", width=160, anchor="w")
        lbl.pack(side="left", padx=10, pady=10)

        btn = ctk.CTkButton(row, text="修改", width=70, height=30, corner_radius=6,
                            fg_color="#3a3a3a", hover_color="#555", text_color="#e0e0e0",
                            font=("Microsoft YaHei", 11),
                            command=lambda rid=a_id, rbtn=None, rlbl=lbl: self._on_rebind(rid, rbtn, rlbl))
        btn.pack(side="right", padx=14, pady=10)

        self._rows[a_id] = (lbl, btn)

    # ---- rebind ----
    def _on_rebind(self, a_id: str, _btn, lbl: ctk.CTkLabel):
        if self._listening_for == a_id:
            self._cancel_listen()
            return
        # 取消前一个
        if self._listening_for:
            self._cancel_listen()

        self._listening_for = a_id
        # 高亮当前行
        for rid, (rlbl, rbtn) in self._rows.items():
            if rid == a_id:
                rbtn.configure(text="取消", fg_color="#ff5252", hover_color="#ff6e6e")
                self._listening_label.configure(
                    text=f"正在监听: {dict(ACTIONS)[a_id]} ...  按下组合键")
                self._start_listen()
            else:
                rbtn.configure(state="disabled")

    def _cancel_listen(self):
        self._stop_listen()
        self._listening_for = None
        self._listening_label.configure(text="")
        for rid, (rlbl, rbtn) in self._rows.items():
            rbtn.configure(state="normal", text="修改", fg_color="#3a3a3a", hover_color="#555")

    # ---- listener ----
    def _start_listen(self):
        self._listen_pressed_mods.clear()
        self._listener = Listener(on_press=self._on_listen_press)
        self._listener.start()

    def _stop_listen(self):
        if self._listener:
            self._listener.stop()
            self._listener = None

    def _on_listen_press(self, key):
        name = _key_label(key)
        if name in ("ctrl", "alt", "shift", "cmd"):
            self._listen_pressed_mods.add(name)
            return

        if name is None:
            return

        # 必须有至少一个修饰键(保持约定: 全局热键=修饰键+普通键)
        mods = sorted(self._listen_pressed_mods)
        combo = "<" + ">+<".join(mods) + ">" if mods else ""
        if name in ("ctrl", "alt", "shift", "cmd"):
            return
        full = "<" + ">+<".join(mods + [name]) + ">"

        a_id = self._listening_for
        self._hotkeys[a_id] = full
        lbl, _btn = self._rows[a_id]
        lbl.configure(text=_combo_to_display(full))
        self._cancel_listen()
        self._stop_listen()

    # ---- actions ----
    def _on_reset(self):
        from core.settings import DEFAULTS
        self._hotkeys = dict(DEFAULTS["hotkeys"])
        for a_id, a_label in ACTIONS:
            lbl, btn = self._rows[a_id]
            lbl.configure(text=_combo_to_display(self._hotkeys[a_id]))

    def _on_save_close(self):
        if self._listening_for:
            self._cancel_listen()
        settings.update_hotkeys(self._hotkeys)
        if self._on_save:
            self._on_save(self._hotkeys)
        self.destroy()
