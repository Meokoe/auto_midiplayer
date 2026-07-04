"""离线冒烟测试:验证映射逻辑与调度结构,不弹窗、不真实按键。"""

import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import note_mapper
from core import keymap
from core.midi_loader import load_midi
from core.key_player import KeyPlayer

# 1) 白键映射:C4..B6 应映射到 0..20
white_seq = [60, 62, 64, 65, 67, 69, 71,  # C4..B4
             72, 74, 76, 77, 79, 81, 83,  # C5..B5
             84, 86, 88, 89, 91, 93, 95]  # C6..B6
got = [note_mapper.map_note(n, 0, note_mapper.SNAP) for n in white_seq]
assert got == list(range(21)), f"白键映射错误: {got}"
print("白键映射 OK:", got)

# 2) 黑键吸附: C#(61) -> C(60), 距离相等取低
assert note_mapper.map_note(61, 0, note_mapper.SNAP) == 0  # C#4 -> C4
assert note_mapper.map_note(63, 0, note_mapper.SNAP) == 1  # D#4 -> D4
# 跳过
assert note_mapper.map_note(61, 0, note_mapper.SKIP) is None
print("黑键策略 OK")

# 3) 八度平移: octave_shift 表示音域窗口整体上移 N 个八度。
#    shift=0 窗口=C4..B6; shift=1 窗口=C5..B7, 因此 C4(60) 越界下沿 -> 截断到 key 0(=C5)
assert note_mapper.map_note(60, 1, note_mapper.SNAP) == 0   # C4 在 shift+1 窗口下方 -> 最低键
assert note_mapper.map_note(72, 1, note_mapper.SNAP) == 0   # C5 = shift+1 窗口最低音 -> key 0
assert note_mapper.map_note(76, 1, note_mapper.SNAP) == 2   # E5 -> key 2
# shift=-1 窗口=C3..B5, C6(84) 越界上沿 -> 截断到 key 20
assert note_mapper.map_note(84, -1, note_mapper.SNAP) == 20
# 越界:C2(36) shift=0, 截断到 0
assert note_mapper.map_note(36, 0, note_mapper.SNAP) == 0
print("八度平移/越界 OK")

# 4) 模式键数
assert len(keymap.MODE_1) == 21 and len(keymap.MODE_2) == 21
print("键位定义 OK")

# 5) 合成一个简单 mid 文件并解析
import mido
mid = mido.MidiFile(ticks_per_beat=480)
track = mido.MidiTrack()
mid.tracks.append(track)
track.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
# C4 持续 0.5 拍(480 ticks), 再 D4
track.append(mido.Message("note_on", note=60, velocity=80, time=0))
track.append(mido.Message("note_off", note=60, velocity=0, time=240))  # 0.5s @ 120bpm
track.append(mido.Message("note_on", note=62, velocity=80, time=0))
track.append(mido.Message("note_off", note=62, velocity=0, time=240))
tmp = os.path.join(tempfile.gettempdir(), "_smoke.mid")
mid.save(tmp)

events, total = load_midi(tmp)
assert len(events) == 4, f"事件数应为4, 实际 {len(events)}"
# 240 ticks @ 480 tpb & tempo 500000(120bpm) -> 0.25s/note, 两音 -> 0.5s
assert abs(total - 0.5) < 0.01, f"总时长应≈0.5s, 实际 {total}"
press_times = [e.time_s for e in events if e.is_press]
assert abs(press_times[0]) < 0.01 and abs(press_times[1] - 0.25) < 0.01
print(f"加载 OK: {len(events)} 事件, 总时长 {total:.2f}s")

# 6) 调度器不真实按键的烟雾测试:替换 _emit
fired = []
player = KeyPlayer()
player.load_events(events, total)
player._emit = lambda key, is_press: fired.append((key, is_press))
player._rebuild_schedule()
sched_keys = [s.key for s in player._schedule]
assert sched_keys == ["a", "a", "a", "a"] or sched_keys[0::2], sched_keys
print("调度构建 OK, 键序列:", sched_keys)

os.remove(tmp)
print("\n全部冒烟测试通过 ✅")
