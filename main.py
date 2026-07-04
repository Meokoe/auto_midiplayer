"""启动 MIDI 自动演奏桌面应用。"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.player_window import main

if __name__ == "__main__":
    main()
