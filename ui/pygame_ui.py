"""
Pygame User Interface for Xiangqi (Cờ Tướng)
Cải tiến:
- Sửa lỗi tràn hình nền gỗ ở phía dưới và bên phải bàn cờ bằng cách render khép kín vào Surface riêng.
- Bộ chọn chế độ chơi dạng danh sách thẻ (Selector), cho phép click chọn trực tiếp.
- Chế độ hiện tại được hiển thị nổi bật với màu sắc tương phản, viền vàng kim và radio button sắc nét.
- Đầy đủ 3+ chế độ: Người vs Máy (Đỏ), Người vs Máy (Đen), Máy vs Máy, Người vs Người.
- Đồ họa SVG sắc nét, gợi ý nước đi, highlight nước vừa đi, cảnh báo chiếu tướng.
- Không sử dụng ký tự emoji ngoài bảng font chuẩn để tránh lỗi hiển thị ô vuông.
"""

import os
import io
import re
import time
import pygame
from game import (
    CoTuongGame, Move,
    RED, BLACK, EMPTY,
    VUA, SI, TUONG, MA, XE, PHAO, TOT
)
from ai.rollout import get_best_move

# Danh mục các chế độ chơi
MODE_HUMAN_VS_AI_RED = "human_vs_ai_red"      # Người đi Đỏ (trước), Máy đi Đen (sau)
MODE_HUMAN_VS_AI_BLACK = "human_vs_ai_black"  # Máy đi Đỏ (trước), Người đi Đen (sau)
MODE_AI_VS_AI = "ai_vs_ai"                    # Máy đấu Máy
MODE_HUMAN_VS_HUMAN = "human_vs_human"        # Hai người chơi

MODE_CONFIGS = [
    (
        MODE_HUMAN_VS_AI_RED,
        "Người (Đỏ) vs Máy (Đen)",
        "Bạn cầm Đỏ đi trước"
    ),
    (
        MODE_HUMAN_VS_AI_BLACK,
        "Máy (Đỏ) vs Người (Đen)",
        "Máy đi trước, bạn cầm Đen"
    ),
    (
        MODE_AI_VS_AI,
        "Máy vs Máy (Bot đấu)",
        "Xem 2 bên AI tự động đấu cờ"
    ),
    (
        MODE_HUMAN_VS_HUMAN,
        "Hai Người Chơi",
        "Đấu đối kháng trực tiếp trên 1 máy"
    ),
]


class XiangqiUI:
    def __init__(self, res_dir: str = "ui/res"):
        pygame.init()
        pygame.font.init()
        pygame.display.set_caption("Cờ Tướng - Xiangqi AI (Pygame)")

        self.res_dir = res_dir
        self.width = 890
        self.height = 645
        self.screen = pygame.display.set_mode((self.width, self.height))
        self.clock = pygame.time.Clock()

        # Board layout parameters
        self.board_x = 24
        self.board_y = 30
        self.grid_ox = 32
        self.grid_oy = 32
        self.cell_w = 57.125
        self.cell_h = 57.111
        self.piece_size = 57

        # Tải tài nguyên và chuẩn bị bề mặt bàn cờ (tránh tràn viền gỗ)
        self._load_fonts()
        self._load_assets()
        self._prepare_board_surfaces()

        # Game state
        self.game = CoTuongGame()
        self.mode = MODE_HUMAN_VS_AI_RED
        self.flip_board = False  # False: Đỏ ở dưới, True: Đen ở dưới
        self.selected_sq: tuple[int, int] | None = None
        self.valid_moves: list[Move] = []
        self.last_move: Move | None = None

        # Lịch sử Undo: lưu danh sách các tuple (game_clone, last_move)
        self.history: list[tuple[CoTuongGame, Move | None]] = [(self.game.clone(), None)]

        # AI state
        self.ai_thinking = False
        self.ai_delay_timer = 0.0
        self.ai_paused = False  # Dành cho chế độ AI vs AI

        # Clickable rects
        self.mode_rects: dict[str, pygame.Rect] = {}
        self.action_rects: dict[str, pygame.Rect] = {}
        self._init_layout()

    def _init_layout(self):
        """Khởi tạo trước các tọa độ hình chữ nhật cho các nút bấm."""
        px = 572
        py = 20
        pw = 296
        status_box_y = py + 62
        status_box_h = 88

        # Mode buttons
        mode_sec_y = status_box_y + status_box_h + 12
        mode_btn_y = mode_sec_y + 24
        mode_btn_h = 40
        mode_gap = 6

        for idx, (m_id, _, _) in enumerate(MODE_CONFIGS):
            self.mode_rects[m_id] = pygame.Rect(px + 14, mode_btn_y + idx * (mode_btn_h + mode_gap), pw - 28, mode_btn_h)

        # Action buttons
        act_sec_y = mode_btn_y + len(MODE_CONFIGS) * (mode_btn_h + mode_gap) + 8
        btn_start_y = act_sec_y + 28
        btn_h = 34
        btn_gap = 7

        for idx, act_id in enumerate(["undo", "restart", "flip", "pause_ai", "step_ai"]):
            self.action_rects[act_id] = pygame.Rect(px + 14, btn_start_y + idx * (btn_h + btn_gap), pw - 28, btn_h)

    def _load_fonts(self):
        font_candidates = ["Segoe UI", "Tahoma", "Arial", "sans-serif"]
        self.font_title = pygame.font.SysFont(font_candidates, 21, bold=True)
        self.font_bold = pygame.font.SysFont(font_candidates, 15, bold=True)
        self.font_mode_title = pygame.font.SysFont(font_candidates, 14, bold=True)
        self.font_mode_sub = pygame.font.SysFont(font_candidates, 11)
        self.font_main = pygame.font.SysFont(font_candidates, 13)
        self.font_status = pygame.font.SysFont(font_candidates, 16, bold=True)
        self.font_small = pygame.font.SysFont(font_candidates, 11)
        self.font_badge = pygame.font.SysFont(font_candidates, 10, bold=True)

    def _load_svg(self, filename: str, target_size: tuple[int, int] | None = None) -> pygame.Surface:
        path = os.path.join(self.res_dir, filename)
        with open(path, "r", encoding="utf-8") as f:
            data = f.read()

        m = re.search(r'viewBox="0 0 (\d+) (\d+)"', data)
        w, h = (m.group(1), m.group(2)) if m else ("57", "57")

        data_mod = re.sub(r'width="[^"]+"', f'width="{w}px"', data, count=1)
        data_mod = re.sub(r'height="[^"]+"', f'height="{h}px"', data_mod, count=1)
        surf = pygame.image.load(io.BytesIO(data_mod.encode("utf-8")))

        if target_size and surf.get_size() != target_size:
            surf = pygame.transform.smoothscale(surf, target_size)
        return surf

    def _load_assets(self):
        self.assets: dict[str, pygame.Surface] = {}

        # Board SVG (521 x 577)
        self.assets["board"] = self._load_svg("board.svg")
        # Selector marker (57 x 57)
        self.assets["oos"] = self._load_svg("oos.svg", (57, 57))

        # Wood texture
        wood_path = os.path.join(self.res_dir, "wood.png")
        if os.path.exists(wood_path):
            self.assets["wood"] = pygame.image.load(wood_path).convert()
        else:
            self.assets["wood"] = None

        # Thinking GIF / icon
        think_path = os.path.join(self.res_dir, "thinking.gif")
        if os.path.exists(think_path):
            self.assets["thinking"] = pygame.image.load(think_path).convert_alpha()
        else:
            self.assets["thinking"] = None

        # Pieces mapping: (player, kind) -> filename
        piece_file_map = {
            (RED, VUA): "rk.svg",
            (RED, SI): "ra.svg",
            (RED, TUONG): "rb.svg",
            (RED, MA): "rn.svg",
            (RED, XE): "rr.svg",
            (RED, PHAO): "rc.svg",
            (RED, TOT): "rp.svg",
            (BLACK, VUA): "bk.svg",
            (BLACK, SI): "ba.svg",
            (BLACK, TUONG): "bb.svg",
            (BLACK, MA): "bn.svg",
            (BLACK, XE): "br.svg",
            (BLACK, PHAO): "bc.svg",
            (BLACK, TOT): "bp.svg",
        }

        for (player, kind), fname in piece_file_map.items():
            key = f"{'r' if player == RED else 'b'}_{kind}"
            self.assets[key] = self._load_svg(fname, (57, 57))

        # Check / mate king SVGs
        self.assets["rkm"] = self._load_svg("rkm.svg", (57, 57))
        self.assets["bkm"] = self._load_svg("bkm.svg", (57, 57))

    def _prepare_board_surfaces(self):
        """
        Tạo Surface bàn cờ khép kín kích thước chuẩn xác 521x577.
        Khắc phục triệt để lỗi vân gỗ bị tràn sang phải và xuống dưới.
        """
        normal = pygame.Surface((521, 577))
        flipped = pygame.Surface((521, 577))

        # Vẽ vân gỗ lặp kín trong đúng phạm vi 521x577 (tự động cắt phần dư)
        if self.assets["wood"]:
            wood_surf = self.assets["wood"]
            ww, wh = wood_surf.get_size()
            for x in range(0, 521, ww):
                for y in range(0, 577, wh):
                    normal.blit(wood_surf, (x, y))
                    flipped.blit(wood_surf, (x, y))
        else:
            normal.fill((234, 194, 130))
            flipped.fill((234, 194, 130))

        # Vẽ lưới cờ lên Surface chuẩn
        board_svg = self.assets["board"]
        normal.blit(board_svg, (0, 0))

        # Xoay ngược 180 độ cho góc nhìn quân Đen
        rotated = pygame.transform.rotate(board_svg, 180)
        flipped.blit(rotated, (0, 0))

        self.board_surf_normal = normal
        self.board_surf_flipped = flipped

    def reset_game(self):
        """Khởi động lại ván cờ mới."""
        self.game = CoTuongGame()
        self.selected_sq = None
        self.valid_moves = []
        self.last_move = None
        self.history = [(self.game.clone(), None)]
        self.ai_thinking = False
        self.ai_delay_timer = 0.0

    def undo_move(self):
        """Đi lại nước cờ (Undo)."""
        if len(self.history) <= 1:
            return

        # Ở chế độ Người vs Máy: lùi 2 bước để giữ lượt của Người
        if self.mode in (MODE_HUMAN_VS_AI_RED, MODE_HUMAN_VS_AI_BLACK):
            if len(self.history) >= 3:
                self.history.pop()
                self.history.pop()
            else:
                self.history.pop()
        else:
            self.history.pop()

        self.game, self.last_move = self.history[-1]
        self.game = self.game.clone()
        self.selected_sq = None
        self.valid_moves = []
        self.ai_thinking = False
        self.ai_delay_timer = 0.0

    def set_mode(self, new_mode: str):
        """Đặt chế độ chơi và khởi động ván mới."""
        if self.mode == new_mode:
            return

        self.mode = new_mode
        # Tự động xoay bàn cờ nếu người chơi cầm quân Đen
        if self.mode == MODE_HUMAN_VS_AI_BLACK:
            self.flip_board = True
        elif self.mode == MODE_HUMAN_VS_AI_RED:
            self.flip_board = False

        self.reset_game()

    def cycle_mode(self):
        """Chuyển sang chế độ tiếp theo (dành cho phím tắt M)."""
        all_modes = [c[0] for c in MODE_CONFIGS]
        curr_idx = all_modes.index(self.mode)
        next_mode = all_modes[(curr_idx + 1) % len(all_modes)]
        self.set_mode(next_mode)

    def is_ai_turn(self) -> bool:
        outcome = self.game.outcome()
        if outcome is not None:
            return False

        if self.mode == MODE_AI_VS_AI:
            return not self.ai_paused
        elif self.mode == MODE_HUMAN_VS_AI_RED:
            return self.game.current_player == BLACK
        elif self.mode == MODE_HUMAN_VS_AI_BLACK:
            return self.game.current_player == RED
        return False

    def sq_to_screen(self, row: int, col: int) -> tuple[int, int]:
        vr = 9 - row if self.flip_board else row
        vc = 8 - col if self.flip_board else col
        px = int(self.board_x + self.grid_ox + vc * self.cell_w)
        py = int(self.board_y + self.grid_oy + vr * self.cell_h)
        return px, py

    def screen_to_sq(self, mx: int, my: int) -> tuple[int, int] | None:
        rx = mx - self.board_x - self.grid_ox
        ry = my - self.board_y - self.grid_oy

        vc = round(rx / self.cell_w)
        vr = round(ry / self.cell_h)

        if not (0 <= vc <= 8 and 0 <= vr <= 9):
            return None

        target_x = vc * self.cell_w
        target_y = vr * self.cell_h
        dist = ((rx - target_x) ** 2 + (ry - target_y) ** 2) ** 0.5
        if dist > self.piece_size * 0.55:
            return None

        col = 8 - vc if self.flip_board else vc
        row = 9 - vr if self.flip_board else vr
        return row, col

    def apply_move(self, move: Move):
        self.game = self.game.play(move)
        self.last_move = move
        self.history.append((self.game.clone(), move))
        self.selected_sq = None
        self.valid_moves = []
        self.ai_thinking = False
        self.ai_delay_timer = time.time()

    def handle_click(self, pos: tuple[int, int]):
        mx, my = pos

        # 1. Kiểm tra click vào danh sách CHỌN CHẾ ĐỘ CHƠI
        for mode_key, rect in self.mode_rects.items():
            if rect.collidepoint(mx, my):
                self.set_mode(mode_key)
                return

        # 2. Kiểm tra click vào CÁC NÚT THAO TÁC
        for act_key, rect in self.action_rects.items():
            if rect.collidepoint(mx, my):
                if act_key == "undo":
                    self.undo_move()
                elif act_key == "restart":
                    self.reset_game()
                elif act_key == "flip":
                    self.flip_board = not self.flip_board
                elif act_key == "pause_ai":
                    self.ai_paused = not self.ai_paused
                elif act_key == "step_ai":
                    if not self.game.outcome():
                        best_m = get_best_move(self.game)
                        if best_m:
                            self.apply_move(best_m)
                return

        # Nếu đang đến lượt máy đi hoặc ván đã kết thúc thì bỏ qua click bàn cờ
        if self.is_ai_turn() or self.game.outcome() is not None:
            return

        # 3. Xử lý click chọn quân / đi cờ trên bàn cờ
        sq = self.screen_to_sq(mx, my)
        if sq is None:
            self.selected_sq = None
            self.valid_moves = []
            return

        row, col = sq
        piece = self.game.board[row][col]

        # Đang có quân được chọn -> Kiểm tra nước đi tới ô click
        if self.selected_sq is not None:
            chosen_move = None
            for m in self.valid_moves:
                if m.dst == sq:
                    chosen_move = m
                    break

            if chosen_move:
                self.apply_move(chosen_move)
                return

        # Chọn quân cờ thuộc phe đang đến lượt
        if piece * self.game.current_player > 0:
            self.selected_sq = sq
            all_legal = self.game.legal_moves()
            self.valid_moves = [m for m in all_legal if m.src == sq]
        else:
            self.selected_sq = None
            self.valid_moves = []

    def update(self):
        if self.is_ai_turn():
            now = time.time()
            if not self.ai_thinking:
                self.ai_thinking = True
                self.ai_delay_timer = now
            else:
                delay = 0.4 if self.mode == MODE_AI_VS_AI else 0.25
                if now - self.ai_delay_timer >= delay:
                    best_m = get_best_move(self.game)
                    if best_m is not None:
                        self.apply_move(best_m)
                    self.ai_thinking = False

    def draw_board(self):
        """Vẽ khung gỗ bao quanh và bề mặt bàn cờ không bị tràn."""
        # Khung viền gỗ tinh tế ôm trọn bàn cờ
        border_pad = 10
        frame_rect = pygame.Rect(
            self.board_x - border_pad,
            self.board_y - border_pad,
            521 + border_pad * 2,
            577 + border_pad * 2
        )
        # Bóng đổ ngoài
        pygame.draw.rect(self.screen, (15, 13, 11), frame_rect.inflate(4, 4), border_radius=8)
        # Viền gỗ sẫm
        pygame.draw.rect(self.screen, (58, 43, 30), frame_rect, border_radius=6)
        pygame.draw.rect(self.screen, (110, 85, 60), frame_rect, width=2, border_radius=6)

        # Vẽ Surface bàn cờ chuẩn xác 521x577 vào đúng vị trí
        board_surf = self.board_surf_flipped if self.flip_board else self.board_surf_normal
        self.screen.blit(board_surf, (self.board_x, self.board_y))

        # Đường viền nét mảnh bao quanh giao diện cờ
        pygame.draw.rect(self.screen, (40, 30, 20), (self.board_x, self.board_y, 521, 577), width=1)

    def draw_highlights(self):
        """Vẽ đánh dấu nước cờ gần nhất, quân đang chọn, và gợi ý nước đi."""
        # 1. Đánh dấu nước đi gần nhất
        if self.last_move:
            for sq in (self.last_move.src, self.last_move.dst):
                cx, cy = self.sq_to_screen(sq[0], sq[1])
                rect = pygame.Rect(cx - 28, cy - 28, 56, 56)
                hl_surf = pygame.Surface((56, 56), pygame.SRCALPHA)
                hl_surf.fill((255, 215, 0, 85))  # Vàng mờ
                self.screen.blit(hl_surf, rect)
                pygame.draw.rect(self.screen, (255, 185, 0, 220), rect, width=2, border_radius=4)

        # 2. Đánh dấu ô đang được chọn
        if self.selected_sq:
            cx, cy = self.sq_to_screen(self.selected_sq[0], self.selected_sq[1])
            oos_icon = self.assets.get("oos")
            if oos_icon:
                self.screen.blit(oos_icon, (cx - 28, cy - 28))
            else:
                rect = pygame.Rect(cx - 28, cy - 28, 56, 56)
                pygame.draw.rect(self.screen, (52, 152, 219), rect, width=3, border_radius=5)

        # 3. Gợi ý các nước đi hợp lệ
        for m in self.valid_moves:
            dr, dc = m.dst
            cx, cy = self.sq_to_screen(dr, dc)
            target_piece = self.game.board[dr][dc]

            hint_surf = pygame.Surface((56, 56), pygame.SRCALPHA)
            if target_piece != 0:
                # Nước ăn quân: vòng tròn đỏ viền dày cảnh báo
                pygame.draw.circle(hint_surf, (231, 76, 60, 200), (28, 28), 24, width=3)
                pygame.draw.circle(hint_surf, (231, 76, 60, 90), (28, 28), 10)
            else:
                # Nước di chuyển bình thường: chấm tròn xanh lá
                pygame.draw.circle(hint_surf, (46, 204, 113, 210), (28, 28), 8)
                pygame.draw.circle(hint_surf, (39, 174, 96, 255), (28, 28), 8, width=2)
            self.screen.blit(hint_surf, (cx - 28, cy - 28))

    def draw_pieces(self):
        """Vẽ các quân cờ và hiệu ứng chiếu tướng."""
        in_check_red = self.game.in_check(RED)
        in_check_black = self.game.in_check(BLACK)

        for r in range(10):
            for c in range(9):
                val = self.game.board[r][c]
                if val == 0:
                    continue

                player = RED if val > 0 else BLACK
                kind = abs(val)
                cx, cy = self.sq_to_screen(r, c)
                top_left = (cx - 28, cy - 28)

                if kind == VUA and ((player == RED and in_check_red) or (player == BLACK and in_check_black)):
                    # Hào quang đỏ quanh Tướng bị chiếu
                    aura = pygame.Surface((64, 64), pygame.SRCALPHA)
                    pygame.draw.circle(aura, (255, 0, 0, 115), (32, 32), 30)
                    self.screen.blit(aura, (cx - 32, cy - 32))

                    check_key = "rkm" if player == RED else "bkm"
                    piece_surf = self.assets.get(check_key) or self.assets.get(f"{'r' if player == RED else 'b'}_{kind}")
                else:
                    piece_surf = self.assets.get(f"{'r' if player == RED else 'b'}_{kind}")

                if piece_surf:
                    self.screen.blit(piece_surf, top_left)

    def draw_panel(self):
        """Vẽ bảng điều khiển bên phải với Bộ chọn chế độ trực quan và nổi bật."""
        px = 572
        py = 20
        pw = 296
        ph = 605

        # Khung panel chính
        panel_rect = pygame.Rect(px, py, pw, ph)
        pygame.draw.rect(self.screen, (34, 31, 28), panel_rect, border_radius=8)
        pygame.draw.rect(self.screen, (70, 64, 56), panel_rect, width=2, border_radius=8)

        # Tiêu đề
        title = self.font_title.render("CỜ TƯỚNG AI", True, (241, 196, 15))
        self.screen.blit(title, (px + (pw - title.get_width()) // 2, py + 12))

        subtitle = self.font_small.render("Chính sách Heuristic / Greedy Rollout", True, (160, 155, 145))
        self.screen.blit(subtitle, (px + (pw - subtitle.get_width()) // 2, py + 38))

        pygame.draw.line(self.screen, (55, 50, 45), (px + 14, py + 54), (px + pw - 14, py + 54))

        # ---------------------------------------------------------------------
        # 1. Thẻ trạng thái trận đấu (Status Box)
        # ---------------------------------------------------------------------
        status_box_y = py + 62
        status_box_h = 88
        status_rect = pygame.Rect(px + 14, status_box_y, pw - 28, status_box_h)
        pygame.draw.rect(self.screen, (24, 21, 19), status_rect, border_radius=6)
        pygame.draw.rect(self.screen, (60, 54, 48), status_rect, width=1, border_radius=6)

        outcome = self.game.outcome()
        curr_p = self.game.current_player

        if outcome is None:
            # Banner lượt đi
            turn_rect = pygame.Rect(px + 24, status_box_y + 10, pw - 48, 28)
            turn_bg = (192, 57, 43) if curr_p == RED else (44, 62, 80)
            pygame.draw.rect(self.screen, turn_bg, turn_rect, border_radius=4)

            # Vẽ chấm tròn chỉ thị phe (thay thế emoji font để không bị lỗi ô vuông)
            dot_color = (255, 80, 80) if curr_p == RED else (220, 220, 220)
            pygame.draw.circle(self.screen, dot_color, (turn_rect.x + 20, turn_rect.centery), 6)
            pygame.draw.circle(self.screen, (255, 255, 255), (turn_rect.x + 20, turn_rect.centery), 6, width=1)

            turn_str = "LƯỢT: QUÂN ĐỎ" if curr_p == RED else "LƯỢT: QUÂN ĐEN"
            turn_txt = self.font_status.render(turn_str, True, (255, 255, 255))
            self.screen.blit(turn_txt, (turn_rect.x + 36, turn_rect.centery - turn_txt.get_height() // 2))

            # Thông báo trạng thái: Chiếu tướng hoặc Đang đấu
            in_check = self.game.in_check(curr_p)
            if in_check:
                check_txt = self.font_bold.render("CHIẾU TƯỚNG! (Nguy cấp)", True, (255, 80, 80))
                self.screen.blit(check_txt, (px + 26, status_box_y + 44))
            else:
                normal_txt = self.font_main.render("Trận đấu đang tiếp diễn...", True, (170, 165, 155))
                self.screen.blit(normal_txt, (px + 26, status_box_y + 44))

            # Thông báo AI đang tính
            if self.is_ai_turn():
                ai_txt = self.font_main.render("AI đang tính nước đi...", True, (243, 156, 18))
                self.screen.blit(ai_txt, (px + 26, status_box_y + 64))
                if self.assets.get("thinking"):
                    self.screen.blit(self.assets["thinking"], (px + 180, status_box_y + 68))
            elif self.mode == MODE_AI_VS_AI and self.ai_paused:
                pause_txt = self.font_main.render("Máy vs Máy: Đang tạm dừng", True, (230, 200, 100))
                self.screen.blit(pause_txt, (px + 26, status_box_y + 64))

        else:
            # Kết quả chung cuộc
            win_rect = pygame.Rect(px + 24, status_box_y + 12, pw - 48, 32)
            pygame.draw.rect(self.screen, (39, 174, 96), win_rect, border_radius=4)

            if outcome == RED:
                res_txt = self.font_status.render("ĐỎ THẮNG! (Chiếu bí)", True, (255, 255, 255))
            elif outcome == BLACK:
                res_txt = self.font_status.render("ĐEN THẮNG! (Chiếu bí)", True, (255, 255, 255))
            else:
                res_txt = self.font_status.render("HÒA CỜ!", True, (255, 255, 255))
            self.screen.blit(res_txt, (win_rect.centerx - res_txt.get_width() // 2, win_rect.centery - win_txt.get_height() // 2))

            remind_txt = self.font_main.render("Nhấn 'Ván Mới' để bắt đầu lại", True, (200, 195, 185))
            self.screen.blit(remind_txt, (px + 26, status_box_y + 56))

        # ---------------------------------------------------------------------
        # 2. Bộ chọn Chế độ chơi (Mode Selector Cards) - Rất nổi bật & trực quan
        # ---------------------------------------------------------------------
        mode_sec_y = status_box_y + status_box_h + 12
        sec_title = self.font_bold.render("CHỌN CHẾ ĐỘ CHƠI:", True, (241, 196, 15))
        self.screen.blit(sec_title, (px + 14, mode_sec_y))

        mode_btn_y = mode_sec_y + 24
        mode_btn_h = 40
        mode_gap = 6
        mouse_pos = pygame.mouse.get_pos()

        for idx, (m_id, m_title, m_desc) in enumerate(MODE_CONFIGS):
            card_rect = pygame.Rect(px + 14, mode_btn_y + idx * (mode_btn_h + mode_gap), pw - 28, mode_btn_h)
            self.mode_rects[m_id] = card_rect

            is_active = (self.mode == m_id)
            is_hover = card_rect.collidepoint(mouse_pos)

            if is_active:
                # Chế độ đang chọn: Nổi bật vượt trội với nền sapphire + viền vàng kim 2px
                pygame.draw.rect(self.screen, (24, 98, 178), card_rect, border_radius=6)
                pygame.draw.rect(self.screen, (255, 215, 0), card_rect, width=2, border_radius=6)

                # Vẽ Radio Button tích chọn màu vàng sáng
                rx, ry = card_rect.x + 18, card_rect.centery
                pygame.draw.circle(self.screen, (255, 215, 0), (rx, ry), 7, width=2)
                pygame.draw.circle(self.screen, (255, 215, 0), (rx, ry), 4)

                title_txt = self.font_mode_title.render(m_title, True, (255, 255, 255))
                self.screen.blit(title_txt, (card_rect.x + 34, card_rect.y + 4))

                sub_txt = self.font_mode_sub.render(m_desc, True, (200, 230, 255))
                self.screen.blit(sub_txt, (card_rect.x + 34, card_rect.y + 21))

            else:
                # Chế độ chưa chọn: màu tối thanh lịch
                card_bg = (48, 44, 40) if is_hover else (30, 27, 25)
                card_border = (125, 115, 105) if is_hover else (56, 51, 46)

                pygame.draw.rect(self.screen, card_bg, card_rect, border_radius=6)
                pygame.draw.rect(self.screen, card_border, card_rect, width=1, border_radius=6)

                # Vẽ Radio Button chưa chọn
                rx, ry = card_rect.x + 18, card_rect.centery
                dot_color = (200, 195, 185) if is_hover else (130, 125, 115)
                pygame.draw.circle(self.screen, dot_color, (rx, ry), 7, width=1)

                text_col = (240, 235, 225) if is_hover else (175, 170, 160)
                title_txt = self.font_mode_title.render(m_title, True, text_col)
                self.screen.blit(title_txt, (card_rect.x + 34, card_rect.y + 4))

                sub_col = (185, 180, 170) if is_hover else (130, 125, 118)
                sub_txt = self.font_mode_sub.render(m_desc, True, sub_col)
                self.screen.blit(sub_txt, (card_rect.x + 34, card_rect.y + 21))

        # Đường phân cách
        act_sec_y = mode_btn_y + len(MODE_CONFIGS) * (mode_btn_h + mode_gap) + 8
        pygame.draw.line(self.screen, (55, 50, 45), (px + 14, act_sec_y), (px + pw - 14, act_sec_y))

        # ---------------------------------------------------------------------
        # 3. Các nút thao tác chức năng (Action Buttons)
        # ---------------------------------------------------------------------
        act_lbl = self.font_bold.render("THAO TÁC:", True, (200, 195, 185))
        self.screen.blit(act_lbl, (px + 14, act_sec_y + 8))

        btn_start_y = act_sec_y + 28
        btn_h = 34
        btn_gap = 7

        action_defs = [
            ("undo", "Đi Lại (Undo)  [U]", (52, 73, 94), (64, 88, 112)),
            ("restart", "Ván Mới (Restart)  [R]", (192, 57, 43), (217, 73, 58)),
            ("flip", "Xoay Bàn Cờ (Flip)  [F]", (108, 122, 137), (127, 140, 141)),
        ]

        if self.mode == MODE_AI_VS_AI:
            p_label = "Tiếp Tục AI  [Space]" if self.ai_paused else "Tạm Dừng AI  [Space]"
            action_defs.append(("pause_ai", p_label, (211, 84, 0), (230, 126, 34)))
        else:
            action_defs.append(("step_ai", "Máy Đi Giúp (Hint)  [Space]", (39, 174, 96), (46, 204, 113)))

        for idx, (b_id, label, col_norm, col_hov) in enumerate(action_defs):
            b_rect = pygame.Rect(px + 14, btn_start_y + idx * (btn_h + btn_gap), pw - 28, btn_h)
            self.action_rects[b_id] = b_rect

            is_hov = b_rect.collidepoint(mouse_pos)
            color = col_hov if is_hov else col_norm

            pygame.draw.rect(self.screen, color, b_rect, border_radius=5)
            pygame.draw.rect(self.screen, (255, 255, 255, 45), b_rect, width=1, border_radius=5)

            txt = self.font_bold.render(label, True, (255, 255, 255))
            self.screen.blit(txt, (b_rect.centerx - txt.get_width() // 2, b_rect.centery - txt.get_height() // 2))

        # Hướng dẫn nhanh ở chân trang
        footer_y = py + ph - 22
        foot_txt = self.font_small.render("Phím tắt: U (Undo) | R (Ván mới) | M (Chế độ) | F (Xoay)", True, (130, 125, 115))
        self.screen.blit(foot_txt, (px + (pw - foot_txt.get_width()) // 2, footer_y))

    def render(self):
        """Vẽ toàn bộ khung hình game."""
        self.screen.fill((22, 19, 17))
        self.draw_board()
        self.draw_highlights()
        self.draw_pieces()
        self.draw_panel()
        pygame.display.flip()

    def run(self):
        """Vòng lặp chính của trò chơi (Main Game Loop)."""
        running = True
        while running:
            self.clock.tick(60)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # Chuột trái
                        self.handle_click(event.pos)

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_u:
                        self.undo_move()
                    elif event.key == pygame.K_r:
                        self.reset_game()
                    elif event.key == pygame.K_m:
                        self.cycle_mode()
                    elif event.key == pygame.K_f:
                        self.flip_board = not self.flip_board
                    elif event.key == pygame.K_SPACE:
                        if self.mode == MODE_AI_VS_AI:
                            self.ai_paused = not self.ai_paused
                        else:
                            if not self.game.outcome():
                                best_m = get_best_move(self.game)
                                if best_m:
                                    self.apply_move(best_m)
                    elif event.key == pygame.K_ESCAPE:
                        self.selected_sq = None
                        self.valid_moves = []

            self.update()
            self.render()

        pygame.quit()
