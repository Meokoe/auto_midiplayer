"""MIDI 音高 → 21 键(3 个八度的白键)映射。

默认音域: MIDI 60(C4) .. 95(B6)? 实际 3 个八度白键 = C4..B6 共 21 个白键。
白键在十二平均律中的音级偏移(以 C 为 0):
  C=0 D=2 E=4 F=5 G=7 A=9 B=11
黑键(半音): C#=1 D#=3 F#=6 G#=8 A#=10

key index 0..20: 0..6=C4..B4, 7..13=C5..B5, 14..20=C6..B6
"""

from __future__ import annotations

# 白键的 MIDI 偏移(在一个八度内,相对 C)
WHITE_OFFSETS_IN_OCTAVE = [0, 2, 4, 5, 7, 9, 11]
WHITE_OFFSET_SET = set(WHITE_OFFSETS_IN_OCTAVE)

BASE_NOTE = 60  # C4,基础八度起点

# 黑键策略
SNAP = "snap"      # 吸附到最近白键
SKIP = "skip"      # 跳过(返回 None)


def _is_black(midi_note: int) -> bool:
    return (midi_note % 12) not in WHITE_OFFSET_SET


def _white_index_global(midi_note: int) -> int:
    """把任意 midi_note 映射到全局白键序号(以 C4 为 0 基准的全局白键索引,可负可大)。

    例如 C4=0, D4=1, ..., B4=6, C5=7。
    用于统一处理八度跨度与越界。
    """
    octave = (midi_note // 12) - (BASE_NOTE // 12)  # 相对 C4 所在八度
    pos_in_octave = WHITE_OFFSETS_IN_OCTAVE.index(midi_note % 12) \
        if (midi_note % 12) in WHITE_OFFSET_SET else -1
    # pos_in_octave 为 -1 时表示黑键,调用方应先处理黑键
    return octave * 7 + pos_in_octave


def _snap_to_white(midi_note: int) -> int:
    """把黑键吸附到最近的相邻白键。距离相等取低的。"""
    octave_base = (midi_note // 12) * 12
    note_in_octave = midi_note % 12
    # 找到夹住它的两个白键
    lower = None
    upper = None
    for off in WHITE_OFFSETS_IN_OCTAVE:
        if off < note_in_octave:
            lower = octave_base + off
        if off > note_in_octave and upper is None:
            upper = octave_base + off
    # 跨八度边界:黑键 A#(11) 的 upper 是下一八度的 C
    if lower is None:
        lower = octave_base - 1  # 上一八度的 B
    if upper is None:
        upper = octave_base + 12  # 下一八度的 C
    dl = midi_note - lower
    du = upper - midi_note
    return lower if dl <= du else upper


def map_note(midi_note: int, octave_shift: int,
             black_key_strategy: str = SNAP) -> int | None:
    """返回 0..20 的 key index,或 None(黑键且策略为 skip,或越界后无法吸附)。

    octave_shift: 整体八度平移(-2..2),作用于基准音域。
    """
    # 处理黑键
    if _is_black(midi_note):
        if black_key_strategy == SKIP:
            return None
        midi_note = _snap_to_white(midi_note)

    # 全局白键索引(以 C4=0)
    g = _white_index_global(midi_note)

    # 基准音域 = C4..B6 => 全局白键索引区间 [0, 20]
    # 受 octave_shift 平移:实际区间 [shift*7, shift*7+20]
    lo = octave_shift * 7
    hi = lo + 20
    if g < lo:
        g = lo
    elif g > hi:
        g = hi
    return g - lo  # 归一化到 0..20


def midi_note_name(midi_note: int) -> str:
    """返回可读音名,如 'C4'。"""
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    octave = (midi_note // 12) - 1
    return f"{names[midi_note % 12]}{octave}"
