"""按键调度器:基于 time.monotonic 的线程化播放,后台用 pynput 模拟按键。

支持实时调速、暂停/恢复、停止、进度跳转。
进度通过 on_progress 回调把当前秒数推给 UI(用于进度条)。
"""

from __future__ import annotations

import threading
import time
import bisect
from dataclasses import dataclass
from pynput.keyboard import Controller

from . import note_mapper
from . import keymap


@dataclass
class _ScheduledKey:
    time_s: float
    key: str            # 'a'..'7' 等
    is_press: bool
    key_idx: int = -1   # 0..20 在映射数组中的位置


PLAY_CHUNK = 0.02  # 秒,sleep 分片粒度,便于及时响应控制


class KeyPlayer:
    def __init__(self, on_progress=None, on_finish=None,
                 on_key_press=None, on_key_release=None):
        self._kb = Controller()
        self._on_progress = on_progress
        self._on_finish = on_finish
        self._on_key_press = on_key_press    # (key_idx: int) -> None
        self._on_key_release = on_key_release  # (key_idx: int) -> None

        self._thread = None
        self._stop_flag = threading.Event()
        self._pause_flag = threading.Event()
        self._pause_flag.set()  # set 表示"未被暂停"

        self._events = []          # 原始 NoteEvent
        self._schedule = []        # _ScheduledKey 列表
        self._time_table = []      # 用于二分 seek 的纯时间数组
        self._total_seconds = 0.0

        self.speed = 1.0
        self.mode = "mode_1"
        self.octave_shift = 0
        self.black_key_strategy = note_mapper.SNAP

        self._base_clock = 0.0     # monotonic 基准
        self._base_pos = 0.0       # base_clock 对应的歌曲秒
        self._pressed = set()      # 当前按住的键,便于收尾释放

        self._seek_gen = 0         # seek 代次,UI seek 时自增,worker 据此重定位 i
        self._last_seek_gen = 0

    # ---------- 事件装载 ----------
    def load_events(self, events, total_seconds):
        self._events = events
        self._total_seconds = total_seconds
        self._rebuild_schedule()

    def _rebuild_schedule(self):
        sched = []
        for ev in self._events:
            idx = note_mapper.map_note(ev.midi_note, self.octave_shift,
                                       self.black_key_strategy)
            if idx is None:
                continue
            if idx < 0 or idx >= keymap.KEY_COUNT:
                continue
            key = keymap.MODES[self.mode][idx]
            sched.append(_ScheduledKey(ev.time_s, key, ev.is_press, idx))
        sched.sort(key=lambda s: (s.time_s, 0 if s.is_press else 1))
        self._schedule = sched
        self._time_table = [s.time_s for s in sched]

    # ---------- 控制 ----------
    def play(self, from_pos=None):
        if not self._schedule and self._total_seconds == 0.0:
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop_flag.clear()
        self._pause_flag.set()
        start = from_pos if from_pos is not None else self._current_pos()
        self._base_clock = time.monotonic()
        self._base_pos = start
        self._seek_gen += 1  # 让 worker 从 start 重新定位
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def pause(self):
        if self._thread and self._thread.is_alive() and self._pause_flag.is_set():
            # 先冻结位置(用当前实时位置),再清标志,使 _current_pos 在暂停期间保持不变
            self._base_pos = self._current_pos()
            self._base_clock = time.monotonic()
            self._pause_flag.clear()

    def resume(self):
        if self._thread and self._thread.is_alive() and not self._pause_flag.is_set():
            self._base_clock = time.monotonic()
            self._pause_flag.set()  # _base_pos 已在 pause 时冻结
        else:
            self.play()

    def stop(self):
        self._stop_flag.set()
        self._pause_flag.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        self._base_pos = 0.0
        self._base_clock = time.monotonic()

    def seek(self, pos):
        """跳转到 pos 秒。播放中跳转:重置基准时间并通知 worker 重定位。"""
        self._base_clock = time.monotonic()
        self._base_pos = pos
        self._seek_gen += 1

    def seek_relative(self, delta_seconds: float) -> float:
        """正=快进, 负=快退。返回新位置(歌曲秒)。"""
        cur = self._current_pos()
        new = max(0.0, min(cur + delta_seconds, self._total_seconds))
        self.seek(new)
        return new

    @property
    def total_seconds(self):
        return self._total_seconds

    def _current_pos(self):
        """实时位置:播放中用 base 推算;暂停/停止时冻结为 base_pos。"""
        if self._pause_flag.is_set():
            return self._base_pos + (time.monotonic() - self._base_clock) * self.speed
        return self._base_pos  # 暂停中,冻结

    def is_playing(self):
        return bool(self._thread and self._thread.is_alive() and self._pause_flag.is_set())

    def is_paused(self):
        return bool(self._thread and self._thread.is_alive() and not self._pause_flag.is_set())

    # ---------- 内部 ----------
    def _first_index_at_or_after(self, pos):
        return bisect.bisect_left(self._time_table, pos)

    def _emit(self, key: str, is_press: bool, key_idx: int = -1):
        try:
            if is_press:
                self._kb.press(key)
                self._pressed.add(key)
                if self._on_key_press and key_idx >= 0:
                    self._on_key_press(key_idx)
            else:
                self._kb.release(key)
                self._pressed.discard(key)
                if self._on_key_release and key_idx >= 0:
                    self._on_key_release(key_idx)
        except Exception:
            pass

    def _run(self):
        i = 0
        last_seek = -1
        last_progress_t = -1.0

        while not self._stop_flag.is_set():
            # 暂停等待
            while not self._pause_flag.is_set() and not self._stop_flag.is_set():
                time.sleep(PLAY_CHUNK)
            if self._stop_flag.is_set():
                break

            # 处理 seek:代次变化则按 base_pos 重新定位 i
            if self._seek_gen != last_seek:
                last_seek = self._seek_gen
                i = self._first_index_at_or_after(self._base_pos)
                # 跳过已过的松键不计,但补发:简化为从该点开始正常推进
                last_progress_t = self._base_pos

            if i >= len(self._schedule):
                # 自然到尾
                break

            sk = self._schedule[i]
            now_t = self._base_pos + (time.monotonic() - self._base_clock) * self.speed

            if sk.time_s > now_t:
                wait = (sk.time_s - now_t) / self.speed if self.speed > 0 else 1.0
                slept = 0.0
                while slept < wait:
                    if self._stop_flag.is_set() or not self._pause_flag.is_set():
                        break
                    if self._seek_gen != last_seek:
                        break  # seek 发生,重新定位
                    time.sleep(min(PLAY_CHUNK, wait - slept))
                    slept += PLAY_CHUNK
                else:
                    self._emit(sk.key, sk.is_press, sk.key_idx)
                    i += 1
                continue
            else:
                # 已到点(可能因暂停落后),补发
                self._emit(sk.key, sk.is_press, sk.key_idx)
                i += 1

            # 推进度回调(~每 50ms)
            cur = self._base_pos + (time.monotonic() - self._base_clock) * self.speed
            if cur - last_progress_t >= 0.05:
                last_progress_t = cur
                if self._on_progress:
                    self._on_progress(min(cur, self._total_seconds))

        # 收尾
        self._release_all()
        if not self._stop_flag.is_set():
            if self._on_progress:
                self._on_progress(self._total_seconds)
            if self._on_finish:
                self._on_finish()

    def _release_all(self):
        for key in list(self._pressed):
            try:
                self._kb.release(key)
            except Exception:
                pass
        self._pressed.clear()
