"""MIDI 播放列表面板: CTkScrollableFrame 列表, 项卡片(文件名/备注/时长), 点击选中加载, 删除&编辑备注。

callback 约定:
  on_select(item: dict)       — 点击卡片选中
  on_load_and_play(item)       — 双击=选中+播放
  on_delete(item, index)
  on_note_change(item, new_note)
  on_import()                  — 外部处理文件对话框+插入列表
"""

from __future__ import annotations

import os
import customtkinter as ctk
from tkinter import messagebox


# 配色
BG_CARD = "#1e1e1e"
BG_CARD_SEL = "#0a3a4a"
BORDER_SEL = "#00d4ff"
BORDER_NORMAL = "#333"
TEXT_PRIMARY = "#e0e0e0"
TEXT_SECONDARY = "#888"
TEXT_ACCENT = "#00d4ff"
BG_DARK = "#121212"
DANGER = "#ff5252"
DANGER_HOVER = "#ff6e6e"


def _fmt(t):
    m, s = divmod(max(0, int(t)), 60)
    return f"{m:02d}:{s:02d}"


class PlaylistPanel(ctk.CTkFrame):
    def __init__(self, master, on_select=None, on_load_and_play=None,
                 on_delete=None, on_note_change=None, on_import=None, **kwargs):
        super().__init__(master, fg_color=BG_DARK, corner_radius=0, **kwargs)

        self._on_select = on_select
        self._on_load_and_play = on_load_and_play
        self._on_delete = on_delete
        self._on_note_change = on_note_change
        self._on_import = on_import

        self._items: list[dict] = []
        self._card_widgets: list[dict] = []  # [{"frame": CTkFrame, "labels": {...}, "index": int}, ...]
        self._selected_index: int = -1

        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self):
        # 标题
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=10, pady=(10, 4))
        ctk.CTkLabel(hdr, text="📋 曲目列表", font=("Microsoft YaHei", 14, "bold"),
                     text_color=TEXT_ACCENT).pack(side="left")

        # 导入按钮
        ctk.CTkButton(hdr, text="＋ 导入", width=70, height=28, corner_radius=6,
                      fg_color="#2a2a2a", hover_color="#3a3a3a", text_color=TEXT_PRIMARY,
                      font=("Microsoft YaHei", 11),
                      command=self._on_import_click).pack(side="right", padx=4)

        # 可滚动区域
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                              scrollbar_button_color="#333",
                                              scrollbar_button_hover_color="#555")
        self._scroll.pack(fill="both", expand=True, padx=6, pady=4)

    # ------------------------------------------------------------------
    def set_items(self, items: list[dict]):
        self._items = items
        self._refresh_cards()

    def get_items(self) -> list[dict]:
        return self._items

    def add_item(self, item: dict):
        self._items.append(item)
        self._refresh_cards()

    def remove_item(self, index: int):
        if 0 <= index < len(self._items):
            self._items.pop(index)
            if self._selected_index == index:
                self._selected_index = -1
            elif self._selected_index > index:
                self._selected_index -= 1
            self._refresh_cards()

    def set_selected(self, index: int):
        self._selected_index = index
        self._refresh_cards()

    # ------------------------------------------------------------------
    def _refresh_cards(self):
        # 清空旧卡片
        for w in self._card_widgets:
            w["frame"].destroy()
        self._card_widgets.clear()

        # 强制更新 ScrollableFrame 内部布局
        try:
            self._scroll.update_idletasks()
        except Exception:
            pass

        for i, item in enumerate(self._items):
            self._create_card(i, item)

    def _create_card(self, index: int, item: dict):
        path = item.get("path", "")
        note = item.get("note", "")
        dur = item.get("duration_s", 0.0)
        name = os.path.basename(path) if path else "(无文件)"
        exists = os.path.exists(path) if path else True

        is_sel = (index == self._selected_index)
        border_color = BORDER_SEL if is_sel else BORDER_NORMAL
        card_bg = BG_CARD_SEL if is_sel else BG_CARD

        frame = ctk.CTkFrame(self._scroll, fg_color=card_bg, corner_radius=10,
                             border_width=1, border_color=border_color)
        frame.pack(fill="x", padx=4, pady=3)

        # ---- 第一行: 文件名 + 删除按钮 ----
        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(8, 2))

        name_color = TEXT_SECONDARY if not exists else TEXT_PRIMARY
        # 截断过长文件名, 保留删除按钮空间(width≈300 - 左右padding - 按钮26)
        max_chars = 22
        display_name = name if len(name) <= max_chars else name[:max_chars-1] + "…"
        name_label = ctk.CTkLabel(top, text=f"🎵 {display_name}" if exists else f"⚠ 已丢失: {name[:18]}",
                                  font=("Microsoft YaHei", 12, "bold"),
                                  text_color=name_color, anchor="w")
        name_label.pack(side="left", fill="x", expand=False)  # 不扩展, 给删除按钮留空间

        del_btn = ctk.CTkButton(top, text="✕", width=26, height=26, corner_radius=5,
                                fg_color="transparent", hover_color="#442222",
                                text_color=DANGER,
                                font=("Consolas", 12),
                                command=lambda idx=index: self._on_delete_click(idx))
        del_btn.pack(side="right", padx=(4, 0))

        # ---- 备注行 ----
        mid = ctk.CTkFrame(frame, fg_color="transparent")
        mid.pack(fill="x", padx=10, pady=(0, 2))
        note_text = note if note else "📝 双击此处添加备注..."
        note_color = TEXT_SECONDARY if not note else TEXT_PRIMARY
        note_label = ctk.CTkLabel(mid, text=note_text, font=("Microsoft YaHei", 10),
                                  text_color=note_color, anchor="w")
        note_label.pack(side="left", fill="x", expand=True)

        # ---- 时长 ----
        bottom = ctk.CTkFrame(frame, fg_color="transparent")
        bottom.pack(fill="x", padx=10, pady=(0, 6))
        ctk.CTkLabel(bottom, text=f"⏱ {_fmt(dur)}", font=("Consolas", 10),
                     text_color=TEXT_SECONDARY, anchor="w").pack(side="left")

        # ---- 事件绑定 ----
        # 卡片本身: 单击选中, 双击选中+播放
        for child in (frame, top, name_label, bottom):
            child.bind("<Button-1>", lambda e, idx=index: self._on_card_click(idx))
            child.bind("<Double-Button-1>", lambda e, idx=index: self._on_card_double(idx))

        # 备注区域: 覆盖单击(不冒泡), 双击→编辑
        def _click_note(e, idx=index):
            self._on_card_click(idx)
            return "break"
        def _dbl_note(e, idx=index):
            self._on_note_double_click(idx)
            return "break"
        for c in (mid, note_label):
            c.bind("<Button-1>", _click_note, add="+")
            c.bind("<Double-Button-1>", _dbl_note, add="+")

        self._card_widgets.append({
            "frame": frame,
            "index": index,
            "note_label": note_label,
        })

    # ---- events ----
    def _on_card_click(self, index: int):
        self._selected_index = index
        self._refresh_cards()
        if self._on_select and 0 <= index < len(self._items):
            self._on_select(self._items[index])

    def _on_card_double(self, index: int):
        self._selected_index = index
        self._refresh_cards()
        if self._on_load_and_play and 0 <= index < len(self._items):
            self._on_load_and_play(self._items[index])

    def _on_delete_click(self, index: int):
        item = self._items[index] if 0 <= index < len(self._items) else None
        name = os.path.basename(item.get("path", "")) if item else ""
        ok = messagebox.askyesno("删除曲目", f"确定从列表中删除「{name}」？\n(不会删除原始文件)")
        if ok and self._on_delete:
            self._on_delete(index)

    def _on_note_double_click(self, index: int):
        if not (0 <= index < len(self._items)):
            return
        item = self._items[index]
        old = item.get("note", "")

        # 自定义 CTkToplevel 编辑弹窗
        dlg = ctk.CTkToplevel()
        dlg.title("编辑备注")
        dlg.geometry("380x180")
        dlg.resizable(False, False)
        dlg.configure(fg_color="#1a1a1a")
        dlg.attributes("-topmost", True)
        try:
            dlg.grab_set()
        except Exception:
            pass

        ctk.CTkLabel(dlg, text="输入备注:", font=("Microsoft YaHei", 13),
                     text_color="#e0e0e0").pack(pady=(18, 8))
        entry = ctk.CTkEntry(dlg, width=320, height=34, corner_radius=8,
                             fg_color="#2a2a2a", border_color="#555",
                             text_color="#e0e0e0", font=("Microsoft YaHei", 13))
        entry.insert(0, old)
        entry.pack(pady=(0, 14))
        entry.focus_set()
        # 选中全部文本方便替换
        entry.select_range(0, "end")

        result = {"value": None}

        def _confirm():
            result["value"] = entry.get().strip()
            dlg.destroy()

        def _cancel():
            dlg.destroy()

        entry.bind("<Return>", lambda e: _confirm())
        entry.bind("<Escape>", lambda e: _cancel())

        bf = ctk.CTkFrame(dlg, fg_color="transparent")
        bf.pack()
        ctk.CTkButton(bf, text="取消", width=100, height=34, corner_radius=8,
                      fg_color="#444", hover_color="#555", text_color="#e0e0e0",
                      font=("Microsoft YaHei", 12), command=_cancel).pack(side="left", padx=8)
        ctk.CTkButton(bf, text="确定", width=100, height=34, corner_radius=8,
                      fg_color="#00e676", hover_color="#00ff7a", text_color="#000",
                      font=("Microsoft YaHei", 12, "bold"), command=_confirm).pack(side="left", padx=8)

        dlg.wait_window()

        new_note = result["value"]
        if new_note is not None and new_note != old:
            item["note"] = new_note
            if self._on_note_change:
                self._on_note_change(index, new_note)
            self._refresh_cards()

    def _on_import_click(self):
        if self._on_import:
            self._on_import()
