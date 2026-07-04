"""主窗 — 左侧播放列表(280px) + 右侧播放器, 全局快捷键, 设置持久化。"""

from __future__ import annotations

import customtkinter as ctk
from tkinter import filedialog, messagebox
import sys
import os
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.midi_loader import load_midi
from core import note_mapper
from core import keymap
from core.key_player import KeyPlayer
from core import settings
from ui.playlist_panel import PlaylistPanel
from ui.settings_window import SettingsWindow
from ui.hotkey_listener import HotkeyListener

# ---------------------------------------------------------------------------
# 配色常量
# ---------------------------------------------------------------------------
ACCENT = "#00d4ff"
ACCENT_HOVER = "#00e5ff"
BG_DARK = "#121212"
BG_CARD = "#1e1e1e"
BG_KEY = "#2a2a2a"
BG_KEY_ACTIVE = "#00d4ff"
TEXT_PRIMARY = "#e0e0e0"
TEXT_SECONDARY = "#888888"
GREEN = "#00e676"
GREEN_HOVER = "#00ff7a"
AMBER = "#ffab00"
AMBER_HOVER = "#ffc400"
RED = "#ff5252"
RED_HOVER = "#ff6e6e"
IMPORT_BG = "#2a2a2a"
IMPORT_HOVER = "#3a3a3a"

# 快进/快退步长
SEEK_STEP = 5.0
SPEED_STEP = 0.1


def _fmt(t):
    m, s = divmod(max(0, int(t)), 60)
    return f"{m:02d}:{s:02d}"


# ---------------------------------------------------------------------------
# 键盘可视化 Canvas
# ---------------------------------------------------------------------------
class PianoKeyboard(ctk.CTkFrame):
    """21 键三排键盘可视化。"""

    KEY_W = 56
    KEY_H = 36
    PAD = 2
    RADIUS = 5

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=BG_CARD, corner_radius=12, **kwargs)
        self._key_rects = []          # [(canvas_id, text_id), ...]
        self._active_set = set()
        self.canvas = ctk.CTkCanvas(self, bg=BG_CARD, highlightthickness=0, height=152)
        self.canvas.pack(fill="both", expand=True, padx=8, pady=8)
        self._draw_keys()

    def _draw_keys(self):
        self.canvas.delete("all")
        self._key_rects = []
        cw, ch, pad, r = self.KEY_W, self.KEY_H, self.PAD, self.RADIUS

        for row_idx, start_idx in enumerate([14, 7, 0]):
            y = 10 + row_idx * (ch + 8)
            label = ["高", "中", "低"][row_idx]
            self.canvas.create_text(4, y + ch / 2, text=label, fill=TEXT_SECONDARY,
                                    font=("Microsoft YaHei", 8), anchor="w")
            for col in range(7):
                ki = start_idx + col
                x = 24 + col * (cw + pad)
                rid = self._create_round_rect(x, y, x + cw, y + ch, r=r, fill=BG_KEY, outline="")
                tid = self.canvas.create_text(x + cw / 2, y + ch / 2,
                                              text=keymap.MODE_1[ki].upper(),
                                              fill=TEXT_PRIMARY, font=("Consolas", 12, "bold"))
                self._key_rects.append((rid, tid))

    def _create_round_rect(self, x1, y1, x2, y2, r=5, **kw):
        pts = [x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1,
               x2, y1, x2, y1 + r, x2, y1 + r, x2, y2 - r,
               x2, y2 - r, x2, y2, x2 - r, y2, x2 - r, y2,
               x1 + r, y2, x1 + r, y2, x1, y2, x1, y2 - r,
               x1, y2 - r, x1, y1 + r, x1, y1 + r, x1, y1]
        return self.canvas.create_polygon(pts, smooth=True, **kw)

    def rebuild_for_mode(self, mode_name):
        keys = keymap.MODES.get(mode_name, keymap.MODE_1)
        for i, (rid, tid) in enumerate(self._key_rects):
            self.canvas.itemconfig(tid, text=keys[i].upper() if i < len(keys) else "")

    def highlight(self, key_idx: int):
        if key_idx >= len(self._key_rects):
            return
        rid, _ = self._key_rects[key_idx]
        self.canvas.itemconfig(rid, fill=BG_KEY_ACTIVE)
        self._active_set.add(key_idx)

    def unhighlight(self, key_idx: int):
        if key_idx >= len(self._key_rects):
            return
        rid, _ = self._key_rects[key_idx]
        self.canvas.itemconfig(rid, fill=BG_KEY)
        self._active_set.discard(key_idx)

    def clear_all(self):
        for ki in list(self._active_set):
            self.unhighlight(ki)


# ---------------------------------------------------------------------------
# 曲目信息面板 — 填充右侧空白,统计 + 音符密度时间线图
# ---------------------------------------------------------------------------
class TrackInfoPanel(ctk.CTkFrame):
    """展示已加载曲目的统计信息 + Canvas 音符密度时间线图。"""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=BG_CARD, corner_radius=14, **kwargs)
        self._events = []
        self._total_s = 0.0
        self._current_s = 0.0

        # header
        ctk.CTkLabel(self, text="📊  曲目信息", font=("Microsoft YaHei", 12, "bold"),
                     text_color=TEXT_SECONDARY).pack(anchor="w", padx=14, pady=(10, 4))

        # 统计卡片行(3 列)
        stats = ctk.CTkFrame(self, fg_color="transparent")
        stats.pack(fill="x", padx=10, pady=4)

        self._stat_total = self._stat_card(stats, "总音符")
        self._stat_total.pack(side="left", expand=True, fill="x", padx=3)
        self._stat_range = self._stat_card(stats, "音域")
        self._stat_range.pack(side="left", expand=True, fill="x", padx=3)
        self._stat_density = self._stat_card(stats, "密度")
        self._stat_density.pack(side="left", expand=True, fill="x", padx=3)

        # 播放进度位置提示
        self._pos_label = ctk.CTkLabel(self, text="", font=("Consolas", 10),
                                       text_color=ACCENT)
        self._pos_label.pack(anchor="w", padx=14, pady=(2, 0))

        # 音符密度图 Canvas
        self._canvas = ctk.CTkCanvas(self, bg=BG_CARD, highlightthickness=0, height=110)
        self._canvas.pack(fill="both", expand=False, padx=6, pady=(4, 8))
        self._canvas.bind("<Configure>", lambda e: self._draw_density())

    def _stat_card(self, parent, title: str) -> ctk.CTkFrame:
        f = ctk.CTkFrame(parent, fg_color="#252525", corner_radius=10)
        ctk.CTkLabel(f, text=title, font=("Microsoft YaHei", 9),
                     text_color=TEXT_SECONDARY).pack(pady=(8, 0))
        lbl = ctk.CTkLabel(f, text="—", font=("Microsoft YaHei", 18, "bold"),
                           text_color=TEXT_PRIMARY)
        lbl.pack(pady=(0, 8))
        f._value_label = lbl
        return f

    def update_events(self, events, total_seconds: float):
        self._events = events
        self._total_s = max(total_seconds, 0.001)

        press_count = sum(1 for e in events if e.is_press)
        low_note = min((e.midi_note for e in events if e.is_press), default=0)
        high_note = max((e.midi_note for e in events if e.is_press), default=0)
        density = press_count / self._total_s if self._total_s > 0 else 0

        from core.note_mapper import midi_note_name
        self._stat_total._value_label.configure(text=str(press_count))
        self._stat_range._value_label.configure(
            text=f"{midi_note_name(low_note)}–{midi_note_name(high_note)}"
            if press_count > 0 else "—")
        self._stat_density._value_label.configure(text=f"{density:.1f}/s")

        self._draw_density()

    def set_progress(self, current_s: float):
        self._current_s = current_s
        self._pos_label.configure(text=f"▶ {_fmt(current_s)} / {_fmt(self._total_s)}")
        self._draw_density()

    def _draw_density(self):
        self._canvas.delete("all")
        w = self._canvas.winfo_width() or 500
        h = 110
        margin = 14
        plot_w = w - 2 * margin
        plot_h = h - 2 * margin - 14  # 底部留标签

        if not self._events or self._total_s == 0:
            self._canvas.create_text(w / 2 - 4, h / 2 - 10, text="暂无数据",
                                     fill=TEXT_SECONDARY, font=("Microsoft YaHei", 10))
            return

        # 分桶统计(每秒)
        buckets = max(1, int(self._total_s) + 1)
        counts = [0] * buckets
        for e in self._events:
            if e.is_press:
                idx = min(buckets - 1, int(e.time_s))
                counts[idx] += 1
        max_c = max(counts) if max(counts) > 0 else 1

        # 基线
        y0 = h - margin - 14
        self._canvas.create_line(margin, y0, margin + plot_w, y0, fill="#444", width=1)

        # ---- 波形连续曲线(渐变填充) ----
        # 绘制由 counts 平滑的折线 + 半透明底部填充, 比裸柱状图更好看
        pts_smooth = []
        for i in range(buckets):
            x = margin + (i / buckets) * plot_w
            bar_h = (counts[i] / max_c) * (plot_h - 4) if max_c > 0 else 0
            pts_smooth.extend([x, y0 - bar_h])

        if len(pts_smooth) >= 4:
            # 底层半透明填充
            fill_pts = [margin, y0]
            for i in range(0, len(pts_smooth), 2):
                fill_pts.extend([pts_smooth[i], pts_smooth[i + 1]])
            fill_pts.extend([margin + plot_w, y0])
            flat = [item for sub in fill_pts for item in (sub if isinstance(sub, list) else [sub])]
            # 简化: 直接用多边形填充
            self._canvas.create_polygon(
                margin, y0,
                *pts_smooth,
                margin + plot_w, y0,
                fill=ACCENT, outline="", width=0, stipple="", state="normal")
            # 覆盖渐变色(用低 alpha 不行在 tk, 故用 stipple 纹理模拟半透明)
            # 改用纯色 + 轮廓线
            self._canvas.delete("all")  # 重建 —— 刚才线条已删
            self._canvas.create_line(margin, y0, margin + plot_w, y0, fill="#444", width=1)

        # ---- 重绘: 柱状 + 波形叠加 ----
        bar_w = max(3, plot_w / buckets - 1)
        for i, c in enumerate(counts):
            if c == 0:
                continue
            bar_h = (c / max_c) * (plot_h - 4)
            if bar_h < 1:
                continue
            x = margin + (i / buckets) * plot_w
            ratio = c / max_c
            r = int(0x00 + ratio * 0x00)
            g = int(0x88 + ratio * (0xd4 - 0x88))
            b = int(0xcc + ratio * (0xff - 0xcc))
            color = f"#{r:02x}{g:02x}{b:02x}"
            self._canvas.create_rectangle(x, y0 - bar_h, x + bar_w, y0,
                                          fill=color, outline="", width=0)

        # ---- 波形折线(亮色描边) ----
        if len(pts_smooth) >= 4:
            self._canvas.create_line(*pts_smooth, fill=ACCENT, width=2, smooth=True)

        # ---- 粒子效果: 当前播放位置附近闪烁粒子 ----
        if self._current_s > 0:
            px = margin + (self._current_s / self._total_s) * plot_w
            # 主竖线
            self._canvas.create_line(px, margin, px, y0, fill="#ff5252", width=2, dash=(4, 2))
            # 顶部发光圆点
            r_dot = 4
            self._canvas.create_oval(px - r_dot, margin - r_dot, px + r_dot, margin + r_dot,
                                     fill=ACCENT, outline="", width=0)
            # 底部三角标记
            tri = [px - 4, y0 + 2, px + 4, y0 + 2, px, y0 + 8]
            self._canvas.create_polygon(*tri, fill=ACCENT, outline="")

        # ---- 已播放区域叠加(淡色蒙版) ----
        if self._current_s > 0:
            ox = margin + (self._current_s / self._total_s) * plot_w
            # 用半透明条纹模拟已播放区域
            self._canvas.create_rectangle(margin, margin, ox, y0,
                                          fill="", outline="", width=0,
                                          stipple="gray12")  # tkinter 内置点阵纹理

        # 坐标标签
        self._canvas.create_text(margin, h - 8, text="0s", anchor="nw",
                                 fill=TEXT_SECONDARY, font=("Consolas", 7))
        self._canvas.create_text(margin + plot_w, h - 8, text=f"{self._total_s:.0f}s", anchor="ne",
                                 fill=TEXT_SECONDARY, font=("Consolas", 7))
        # 当前播放位置秒数
        if self._current_s > 0:
            self._canvas.create_text(px, h - 8, text=f"{self._current_s:.1f}s", anchor="s",
                                     fill=ACCENT, font=("Consolas", 8, "bold"))
        self._canvas.create_text(w / 2, 10, text="音符密度时间线", anchor="n",
                                 fill=TEXT_SECONDARY, font=("Microsoft YaHei", 8))


# ---------------------------------------------------------------------------
# 主窗口
# ---------------------------------------------------------------------------
class PlayerWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("MIDI 自动演奏")
        self.geometry("1100x700")
        self.resizable(True, True)
        self.minsize(1000, 620)

        ctk.set_appearance_mode("dark")
        self.configure(fg_color=BG_DARK)

        # 全局热键监听
        self._hotkey_listener = HotkeyListener()

        # player
        self.player = KeyPlayer(
            on_progress=self._on_progress,
            on_finish=self._on_finish,
            on_key_press=self._on_key_press,
            on_key_release=self._on_key_release,
        )

        self._cfg = settings.load()
        self._seeking = False
        self._current_playlist_idx = -1

        self._build_ui()
        self._restore_playlist()
        self._start_hotkeys()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ==================================================================
    # UI 构建
    # ==================================================================
    def _build_ui(self):
        # -- header --
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 4))

        ctk.CTkLabel(header, text="🎵  MIDI 自动演奏", font=("Microsoft YaHei", 20, "bold"),
                     text_color=ACCENT).pack(side="left")

        # gear 按钮
        ctk.CTkButton(header, text="⚙  设置", width=80, height=30, corner_radius=7,
                      fg_color="#2a2a2a", hover_color="#444", text_color=TEXT_PRIMARY,
                      font=("Microsoft YaHei", 11),
                      command=self._on_open_settings).pack(side="right", padx=6)

        self.file_label = ctk.CTkLabel(header, text="", font=("Microsoft YaHei", 11),
                                       text_color=TEXT_SECONDARY)
        self.file_label.pack(side="right", padx=10)

        # ---- 主体: 左列表面板 + 右播放器 ----
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=(4, 8))

        # 左侧列表
        self.playlist_panel = PlaylistPanel(
            body, width=300,
            on_select=self._on_playlist_select,
            on_load_and_play=self._on_playlist_load_and_play,
            on_delete=self._on_playlist_delete,
            on_note_change=self._on_playlist_note_change,
            on_import=self._on_import,
        )
        self.playlist_panel.pack(side="left", fill="y", padx=(0, 8))

        # 右侧播放器区域
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)

        self._build_player_area(right)

    def _build_player_area(self, parent):
        # 上排: 设置卡 + 键盘可视化
        top_area = ctk.CTkFrame(parent, fg_color="transparent")
        top_area.pack(fill="x", pady=(0, 0))

        # -- 设置卡片(左) --
        card = ctk.CTkFrame(top_area, fg_color=BG_CARD, corner_radius=14)
        card.pack(fill="x", pady=(0, 4))

        # 模式
        ctk.CTkLabel(card, text="按键模式", font=("Microsoft YaHei", 11, "bold"),
                     text_color=TEXT_SECONDARY).grid(row=0, column=0, sticky="w", padx=14, pady=(10, 2))
        self.mode_var = ctk.StringVar(value="mode_1")
        mf = ctk.CTkFrame(card, fg_color="transparent")
        mf.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 6))
        for text, val in [("模式1  高:A-J  中:Q-U  低:1-7", "mode_1"),
                          ("模式2  高:Q-U  中:A-J  低:Z-M", "mode_2")]:
            ctk.CTkRadioButton(mf, text=text, variable=self.mode_var, value=val,
                               fg_color=ACCENT, text_color=TEXT_PRIMARY,
                               font=("Microsoft YaHei", 11),
                               command=self._on_options_changed).pack(anchor="w", pady=2)

        # 黑键
        ctk.CTkLabel(card, text="黑键策略", font=("Microsoft YaHei", 11, "bold"),
                     text_color=TEXT_SECONDARY).grid(row=0, column=1, sticky="w", padx=14, pady=(10, 2))
        self.bk_combo = ctk.CTkComboBox(card, values=["吸附", "跳过"], width=90, height=28,
                                        fg_color=BG_KEY, border_color="#444",
                                        button_color=ACCENT, dropdown_fg_color=BG_KEY,
                                        text_color=TEXT_PRIMARY,
                                        font=("Microsoft YaHei", 11),
                                        command=lambda _: self._on_options_changed())
        self.bk_combo.set("吸附")
        self.bk_combo.grid(row=1, column=1, sticky="w", padx=14, pady=(0, 6))

        # 八度偏移
        ctk.CTkLabel(card, text="八度偏移", font=("Microsoft YaHei", 11, "bold"),
                     text_color=TEXT_SECONDARY).grid(row=0, column=2, sticky="w", padx=14, pady=(10, 2))
        oct_f = ctk.CTkFrame(card, fg_color="transparent")
        oct_f.grid(row=1, column=2, sticky="w", padx=14, pady=(0, 6))
        self.oct_var = ctk.IntVar(value=0)
        ctk.CTkButton(oct_f, text="−", width=26, height=26, corner_radius=5,
                      fg_color=BG_KEY, hover_color="#444", text_color=TEXT_PRIMARY,
                      font=("Consolas", 13, "bold"), command=self._oct_down).pack(side="left", padx=1)
        self.oct_label = ctk.CTkLabel(oct_f, text=" 0 ", font=("Consolas", 13, "bold"),
                                      text_color=ACCENT, width=24)
        self.oct_label.pack(side="left", padx=2)
        ctk.CTkButton(oct_f, text="+", width=26, height=26, corner_radius=5,
                      fg_color=BG_KEY, hover_color="#444", text_color=TEXT_PRIMARY,
                      font=("Consolas", 13, "bold"), command=self._oct_up).pack(side="left", padx=1)

        # 速度
        ctk.CTkLabel(card, text="播放速度", font=("Microsoft YaHei", 11, "bold"),
                     text_color=TEXT_SECONDARY).grid(row=0, column=3, sticky="w", padx=14, pady=(10, 2))
        spd_f = ctk.CTkFrame(card, fg_color="transparent")
        spd_f.grid(row=1, column=3, sticky="w", padx=14, pady=(0, 6))
        self.speed_var = ctk.DoubleVar(value=1.0)
        self.speed_slider = ctk.CTkSlider(spd_f, from_=0.25, to=2.0, width=120,
                                          progress_color=ACCENT, button_color=ACCENT,
                                          button_hover_color=ACCENT_HOVER,
                                          variable=self.speed_var,
                                          command=self._on_speed_change)
        self.speed_slider.pack(side="left", padx=(0, 6))
        self.speed_label = ctk.CTkLabel(spd_f, text="1.00x", font=("Consolas", 11, "bold"),
                                        text_color=ACCENT, width=40)
        self.speed_label.pack(side="left")

        # -- 键盘可视化(左侧) --
        self.keyboard = PianoKeyboard(parent)
        self.keyboard.pack(fill="x", pady=(4, 4))

        # -- 进度 --
        pc = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=14)
        pc.pack(fill="x", pady=(2, 4))

        self.time_label = ctk.CTkLabel(pc, text="00:00 / 00:00",
                                       font=("Consolas", 16, "bold"), text_color=TEXT_PRIMARY)
        self.time_label.pack(pady=(8, 2))

        self.progress = ctk.CTkSlider(pc, from_=0, to=100,
                                      progress_color=ACCENT, button_color=ACCENT,
                                      button_hover_color=ACCENT_HOVER, height=12,
                                      command=self._on_progress_drag)
        self.progress.set(0)
        self.progress.pack(fill="x", padx=14, pady=(0, 6))
        self.progress.bind("<ButtonRelease-1>", self._on_progress_release)

        # -- 控制按钮 --
        ctrl = ctk.CTkFrame(parent, fg_color="transparent")
        ctrl.pack(pady=(2, 4))

        self.play_btn = ctk.CTkButton(ctrl, text="▶  播放", width=90, height=36,
                                      corner_radius=10, fg_color=GREEN,
                                      hover_color=GREEN_HOVER,
                                      text_color="#000", font=("Microsoft YaHei", 13, "bold"),
                                      command=self._on_play)
        self.play_btn.pack(side="left", padx=7)

        self.pause_btn = ctk.CTkButton(ctrl, text="⏸  暂停", width=90, height=36,
                                       corner_radius=10, fg_color=AMBER,
                                       hover_color=AMBER_HOVER,
                                       text_color="#000", font=("Microsoft YaHei", 13, "bold"),
                                       command=self._on_pause)
        self.pause_btn.pack(side="left", padx=7)

        self.stop_btn = ctk.CTkButton(ctrl, text="⏹  停止", width=90, height=36,
                                      corner_radius=10, fg_color=RED,
                                      hover_color=RED_HOVER,
                                      text_color="#fff", font=("Microsoft YaHei", 13, "bold"),
                                      command=self._on_stop)
        self.stop_btn.pack(side="left", padx=7)

        # 提示
        ctk.CTkLabel(parent, text="💡 点播放后即刻切到目标窗口,全局按键需焦点窗口才能接收。",
                     font=("Microsoft YaHei", 9), text_color=TEXT_SECONDARY).pack()

        # -- 曲目信息 + 音符密度图 --
        self._info_panel = TrackInfoPanel(parent)
        self._info_panel.pack(fill="both", expand=True, pady=(4, 0))

    # ==================================================================
    # 播放列表回调
    # ==================================================================
    def _on_import(self):
        path = filedialog.askopenfilename(
            title="选择 MIDI 文件",
            filetypes=[("MIDI 文件", "*.mid *.midi"), ("所有文件", "*.*")])
        if not path:
            return
        self._import_and_add(path)

    def _import_and_add(self, path: str):
        try:
            events, total = load_midi(path)
        except Exception as e:
            messagebox.showerror("导入失败", f"无法解析:\n{e}")
            return
        if not events:
            messagebox.showwarning("空文件", "该 MIDI 文件未包含音符事件。")
            return

        item = {"path": path, "note": "", "duration_s": total}
        self.playlist_panel.add_item(item)
        self._sync_playlist_to_settings()

    def _on_playlist_select(self, item: dict):
        self._load_item(item)

    def _on_playlist_load_and_play(self, item: dict):
        self._load_item(item)
        self._on_play()

    def _load_item(self, item: dict):
        path = item.get("path", "")
        if not path or not os.path.exists(path):
            messagebox.showwarning("文件丢失", "该文件不存在,可能已被移动或删除。")
            return
        try:
            events, total = load_midi(path)
        except Exception as e:
            messagebox.showerror("加载失败", f"无法解析:\n{e}")
            return
        self.player.stop()
        self.player.load_events(events, total)
        self.file_label.configure(text=os.path.basename(path))
        self.progress.configure(to=max(total, 0.001))
        self.progress.set(0)
        self.time_label.configure(text=f"00:00 / {_fmt(total)}")
        self._on_options_changed()
        self._info_panel.update_events(events, total)  # 更新曲目信息面板

    def _on_playlist_delete(self, index: int):
        self.playlist_panel.remove_item(index)
        self._sync_playlist_to_settings()

    def _on_playlist_note_change(self, index: int, new_note: str):
        self._sync_playlist_to_settings()

    def _sync_playlist_to_settings(self):
        settings.update_playlist(self.playlist_panel.get_items())

    def _restore_playlist(self):
        items = self._cfg.get("playlist", [])
        valid = []
        for it in items:
            if isinstance(it, dict) and "path" in it:
                valid.append(it)
        self.playlist_panel.set_items(valid)

    # ==================================================================
    # 快捷键
    # ==================================================================
    def _start_hotkeys(self):
        hk = self._cfg.get("hotkeys", {})
        self._apply_hotkeys(hk)
        self._hotkey_listener.start(self._build_handler_map(hk))

    def _build_handler_map(self, hk: dict) -> dict:
        return {
            hk.get("play_pause", ""):  self._hk_play_pause,
            hk.get("stop", ""):        self._hk_stop,
            hk.get("forward", ""):     self._hk_forward,
            hk.get("backward", ""):    self._hk_backward,
            hk.get("speed_up", ""):    self._hk_speed_up,
            hk.get("speed_down", ""):  self._hk_speed_down,
        }

    def _apply_hotkeys(self, hk: dict):
        self._hotkey_listener.reload(self._build_handler_map(hk))

    def _hk_play_pause(self):
        self.after(0, self._on_pause)

    def _hk_stop(self):
        self.after(0, self._on_stop)

    def _hk_forward(self):
        self.after(0, lambda: self.player.seek_relative(SEEK_STEP))

    def _hk_backward(self):
        self.after(0, lambda: self.player.seek_relative(-SEEK_STEP))

    def _hk_speed_up(self):
        def _do():
            new = min(2.0, self.speed_var.get() + SPEED_STEP)
            self.speed_var.set(new)
            self.speed_label.configure(text=f"{new:.2f}x")
            self._on_options_changed()
        self.after(0, _do)

    def _hk_speed_down(self):
        def _do():
            new = max(0.25, self.speed_var.get() - SPEED_STEP)
            self.speed_var.set(new)
            self.speed_label.configure(text=f"{new:.2f}x")
            self._on_options_changed()
        self.after(0, _do)

    # ==================================================================
    # 设置窗口
    # ==================================================================
    def _on_open_settings(self):
        hk = self._cfg.get("hotkeys", settings.DEFAULTS["hotkeys"])
        SettingsWindow(self, hk, on_save=self._on_hotkeys_changed)

    def _on_hotkeys_changed(self, new_hk: dict):
        self._cfg["hotkeys"] = new_hk
        self._apply_hotkeys(new_hk)

    # ==================================================================
    # 八度 ±
    # ==================================================================
    def _oct_down(self):
        v = self.oct_var.get()
        if v > -2:
            self.oct_var.set(v - 1)
            self.oct_label.configure(text=f"{v-1}")
            self._on_options_changed()

    def _oct_up(self):
        v = self.oct_var.get()
        if v < 2:
            self.oct_var.set(v + 1)
            self.oct_label.configure(text=f" {v+1}" if v + 1 >= 0 else f"{v+1}")
            self._on_options_changed()

    # ==================================================================
    # 播放器事件
    # ==================================================================
    def _on_options_changed(self):
        bk = note_mapper.SNAP if self.bk_combo.get() == "吸附" else note_mapper.SKIP
        self.player.black_key_strategy = bk
        self.player.octave_shift = int(self.oct_var.get())
        self.player.mode = self.mode_var.get()
        self.player.speed = float(self.speed_var.get())
        self.player._rebuild_schedule()
        self.keyboard.rebuild_for_mode(self.mode_var.get())

    def _on_speed_change(self, val):
        v = round(float(val), 2)
        self.speed_label.configure(text=f"{v:.2f}x")
        self._on_options_changed()

    def _on_play(self):
        if not self.player._schedule and self.player.total_seconds == 0:
            messagebox.showinfo("提示", "请先从列表中选择或导入 MIDI 文件。")
            return
        self._on_options_changed()
        self.keyboard.clear_all()
        self.player.play(from_pos=float(self.progress.get()))

    def _on_pause(self):
        if self.player.is_playing():
            self.player.pause()
        elif self.player.is_paused():
            self.keyboard.clear_all()
            self.player.resume()

    def _on_stop(self):
        self.player.stop()
        self.keyboard.clear_all()
        self.progress.set(0)
        self.time_label.configure(text=f"00:00 / {_fmt(self.player.total_seconds)}")

    def _on_progress_drag(self, val):
        self._seeking = True
        t = float(val)
        self.time_label.configure(text=f"{_fmt(t)} / {_fmt(self.player.total_seconds)}")

    def _on_progress_release(self, _evt):
        self._seeking = False
        self.player.seek(float(self.progress.get()))

    def _on_progress(self, t):
        if self._seeking:
            return
        self.progress.set(min(t, self.player.total_seconds))
        self.time_label.configure(text=f"{_fmt(t)} / {_fmt(self.player.total_seconds)}")
        self._info_panel.set_progress(t)

    def _on_finish(self):
        self.progress.set(self.player.total_seconds)
        self.time_label.configure(
            text=f"{_fmt(self.player.total_seconds)} / {_fmt(self.player.total_seconds)}")
        self.keyboard.clear_all()

    def _on_key_press(self, key_idx: int):
        self.after(0, lambda: self.keyboard.highlight(key_idx))

    def _on_key_release(self, key_idx: int):
        self.after(0, lambda: self.keyboard.unhighlight(key_idx))

    # ==================================================================
    # 生命周期
    # ==================================================================
    def _on_close(self):
        self._sync_playlist_to_settings()
        self._hotkey_listener.stop()
        try:
            self.player.stop()
        except Exception:
            pass
        self.destroy()

    def destroy(self):
        try:
            self.player.stop()
        except Exception:
            pass
        try:
            self._hotkey_listener.stop()
        except Exception:
            pass
        super().destroy()


def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = PlayerWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
