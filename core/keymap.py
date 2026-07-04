"""两种 21 键模式的键位定义。

key index 0..20 顺序对应从低到高的 3 个八度:
  0..6   = 低八度 do re mi fa sol la ti
  7..13  = 中八度
  14..20 = 高八度

模式1  low=1-7  mid=Q-U  high=A-J
模式2  low=Z-M  mid=A-J  high=Q-U

界面显示从上到下: 高八度(第一排) → 中八度(第二排) → 低八度(第三排)
"""

MODE_1 = ["1", "2", "3", "4", "5", "6", "7",
          "q", "w", "e", "r", "t", "y", "u",
          "a", "s", "d", "f", "g", "h", "j"]

MODE_2 = ["z", "x", "c", "v", "b", "n", "m",
          "a", "s", "d", "f", "g", "h", "j",
          "q", "w", "e", "r", "t", "y", "u"]

MODES = {"mode_1": MODE_1, "mode_2": MODE_2}

MODE_LABELS = {"mode_1": "模式1 (A-J, Q-U, 1-7)", "mode_2": "模式2 (Z-M, A-J, Q-U)"}
KEY_COUNT = len(MODE_1)
