"""
Chương trình chính khởi chạy Game Cờ Tướng (Xiangqi) với AI Heuristic Rollout
Hỗ trợ:
- Chế độ 1: Người vs Máy (Người đi Đỏ)
- Chế độ 2: Người vs Máy (Người đi Đen)
- Chế độ 3: Máy vs Máy (AI vs AI)
- Chế độ 4: Người vs Người (2 người chơi)
"""

import sys
import argparse
from ui.pygame_ui import (
    XiangqiUI,
    MODE_HUMAN_VS_AI_RED,
    MODE_HUMAN_VS_AI_BLACK,
    MODE_AI_VS_AI,
    MODE_HUMAN_VS_HUMAN
)


def parse_args():
    parser = argparse.ArgumentParser(description="Game Cờ Tướng có AI hỗ trợ (Xiangqi)")
    parser.add_argument(
        "--mode",
        choices=["human_red", "human_black", "ai_vs_ai", "human_vs_human"],
        default="human_red",
        help="Chế độ chơi ban đầu (mặc định: human_red)"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    mode_map = {
        "human_red": MODE_HUMAN_VS_AI_RED,
        "human_black": MODE_HUMAN_VS_AI_BLACK,
        "ai_vs_ai": MODE_AI_VS_AI,
        "human_vs_human": MODE_HUMAN_VS_HUMAN,
    }

    initial_mode = mode_map.get(args.mode, MODE_HUMAN_VS_AI_RED)
    
    # Khởi chạy giao diện Pygame
    app = XiangqiUI()
    app.set_mode(initial_mode)
    app.run()


if __name__ == "__main__":
    main()
