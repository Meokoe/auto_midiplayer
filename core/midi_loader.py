"""用 mido 解析 MIDI 文件,合并多 track,把 ticks 换算为秒,产出统一事件列表。

每个 note_on(velocity>0) 与 note_off(或 velocity=0 的 note_on) 配对成 Press/Release。
为简单稳健起见,直接产出按 absolute_time 排序的 (time_s, midi_note, is_press) 事件流,
由 key_player 在播放时按时间触发。
"""

from __future__ import annotations

from dataclasses import dataclass
import mido


@dataclass
class NoteEvent:
    time_s: float       # 相对歌曲起点的秒数
    midi_note: int      # 0..127
    is_press: bool      # True=按下, False=松开


def _ticks_to_seconds(ticks: int, ticks_per_beat: int, tempo_us_per_beat: int) -> float:
    """把 MIDI ticks 换算成秒。tempo 单位是微秒/四分音符。"""
    return mido.tick2second(ticks, ticks_per_beat, tempo_us_per_beat)


def load_midi(path: str):
    """返回 (events: list[NoteEvent], total_seconds: float)。

    合并所有 track,按绝对时间排序。
    """
    mid = mido.MidiFile(path)
    tpb = mid.ticks_per_beat if mid.ticks_per_beat else 480
    tempo = 500000  # 默认 120 BPM

    events: list[NoteEvent] = []
    total_seconds = 0.0

    for track in mid.tracks:
        abs_ticks = 0
        # tempo 可能中途变化,逐事件更新
        for msg in track:
            abs_ticks += msg.time
            if msg.type == "set_tempo":
                tempo = msg.tempo
                continue
            if msg.type == "note_on" and msg.velocity > 0:
                t = _ticks_to_seconds(abs_ticks, tpb, tempo)
                events.append(NoteEvent(t, msg.note, True))
                total_seconds = max(total_seconds, t)
            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                t = _ticks_to_seconds(abs_ticks, tpb, tempo)
                events.append(NoteEvent(t, msg.note, False))
                total_seconds = max(total_seconds, t)

    events.sort(key=lambda e: (e.time_s, 0 if e.is_press else 1))
    return events, total_seconds
