"""严谨端到端:慢速 + 长曲,实时验证 pause/resume/seek/stop。真实 pynput(无目标窗口,不报错即过)。"""

from __future__ import annotations
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mido
from core.midi_loader import load_midi
from core.key_player import KeyPlayer

# 合成 10 个音, 每音 0.4s -> 总 4.0s
mid = mido.MidiFile(ticks_per_beat=480)
tr = mido.MidiTrack(); mid.tracks.append(tr)
tr.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
for i, n in enumerate([60,62,64,65,67,69,71,72,74,76]):
    tr.append(mido.Message("note_on", note=n, velocity=80, time=0))
    tr.append(mido.Message("note_off", note=n, velocity=0, time=192))  # 0.4s
tmp = os.path.join(os.environ.get("TEMP", "/tmp"), "_e2e2.mid")
mid.save(tmp)

events, total = load_midi(tmp)
print(f"loaded {len(events)} events, total {total:.2f}s")
assert abs(total - 2.0) < 0.01

progress_log = []
p = KeyPlayer(on_progress=lambda t: progress_log.append(round(t,2)),
              on_finish=lambda: print("[finish]"))
p.load_events(events, total)
p.speed = 1.0
p.play(from_pos=0)

time.sleep(1.0)
print(f"after 1s play, is_playing={p.is_playing()}, pos≈{p._current_pos():.2f}")
assert p.is_playing()
assert 0.8 < p._current_pos() < 1.3

# 暂停 0.5s,确认位置冻结
p.pause()
t0 = p._current_pos()
time.sleep(0.5)
t1 = p._current_pos()
print(f"paused: pos frozen {t0:.2f} -> {t1:.2f}, is_paused={p.is_paused()}")
assert abs(t1 - t0) < 0.02
assert p.is_paused()

# 恢复,再走 0.5s,确认位置继续前进
p.resume()
time.sleep(0.5)
t2 = p._current_pos()
print(f"resumed: pos advanced to {t2:.2f}, is_playing={p.is_playing()}")
assert p.is_playing()
assert t2 > t0 + 0.3

# seek 到 1.4s
p.seek(1.4)
time.sleep(0.3)
t3 = p._current_pos()
print(f"seek 1.4 -> pos {t3:.2f}")
assert 1.4 <= t3 < 1.8

p.stop()
print(f"stopped, is_playing={p.is_playing()}")
assert not p.is_playing()

# 验证进度回调确有触发
assert len(progress_log) > 0, "进度回调未触发"
print(f"进度回调累计 {len(progress_log)} 次, 末值 {progress_log[-1]}")
os.remove(tmp)
print("\nE2E 严谨测试通过 ✅ (真实按键触发需人工在目标窗口验证)")
