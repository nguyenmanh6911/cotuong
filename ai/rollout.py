"""
Heuristic / Greedy Rollout Policy for Xiangqi (Cờ Tướng)
Chiến lược đi cờ:
- Ưu tiên ăn quân có giá trị cao (Xe > Pháo > Mã > Tốt...), MVV-LVA.
- Thoát chiếu và giải tỏa uy hiếp khi bị tấn công.
- Tránh đi quân vào các ô bị đối phương nhắm tới (tránh mất quân lớn).
- Tích điểm vị trí: Phát triển Xe/Mã, chiếm trung lộ, Tốt qua sông.
"""

import random
from game import (
    RED, BLACK, EMPTY,
    VUA, SI, TUONG, MA, XE, PHAO, TOT,
    crossed_river
)

# Giá trị cơ bản của các quân cờ
PIECE_VALUES = {
    VUA: 10000,
    XE: 900,
    PHAO: 450,
    MA: 400,
    SI: 200,
    TUONG: 200,
    TOT: 100
}


def piece_value(kind: int, row: int | None = None, player: int | None = None) -> int:
    """Trả về giá trị lượng hóa của quân cờ, tính thêm vị trí (Tốt qua sông)."""
    base = PIECE_VALUES.get(kind, 0)
    if kind == TOT and row is not None and player is not None:
        if crossed_river(row, player):
            return base + 120  # Tốt đã qua sông mạnh gần gấp đôi
    return base


def is_square_attacked(game, square: tuple[int, int], by_player: int) -> bool:
    """Kiểm tra ô square có đang bị quân của bên by_player ngắm tới hay không."""
    for move in game.pseudo_moves(by_player):
        if move.dst == square:
            return True
    return False


def score_move(game, move) -> float:
    """
    Đánh giá điểm số của nước đi cho người chơi hiện tại:
    - Ăn quân có lợi (Most Valuable Victim - Least Valuable Attacker)
    - Tránh tự sát (không đi quân lớn vào ô đối phương đang kiểm soát)
    - Giải tỏa khi quân bị uy hiếp
    - Chiếu tướng đối phương
    - Điểm vị trí chiến lược
    """
    player = game.current_player
    opponent = -player
    sr, sc = move.src
    dr, dc = move.dst

    moving_code = game.board[sr][sc]
    target_code = game.board[dr][dc]
    kind = abs(moving_code)
    target_kind = abs(target_code) if target_code else 0

    next_state = game._after(move)
    outcome = next_state.outcome()

    # 1. Thắng ngay lập tức
    if outcome == player:
        return 100000.0
    if outcome == EMPTY:
        return -100.0  # Tránh hòa cờ lặp lại nếu có nước đi khác

    score = 0.0

    # 2. Chiếu tướng đối phương
    if next_state.in_check(opponent):
        score += 85.0

    # 3. Tính giá trị ăn quân và an toàn nước đi
    target_val = piece_value(target_kind, dr, opponent) if target_kind > 0 else 0
    moving_val = piece_value(kind, sr, player)

    # Kiểm tra ô đích có bị đối phương tấn công lại không trong trạng thái kế tiếp
    dest_attacked = is_square_attacked(next_state, (dr, dc), opponent)
    # Kiểm tra ô nguồn trước khi đi có đang bị ngắm không
    was_attacked = is_square_attacked(game, (sr, sc), opponent)

    if target_kind > 0:
        if dest_attacked:
            # Đổi quân: tính chênh lệch giá trị
            exchange_diff = target_val - moving_val
            if exchange_diff >= 0:
                score += exchange_diff * 8 + 300.0
            else:
                score += exchange_diff * 10  # Đổi quân bất lợi (ví dụ Xe đổi Tốt)
        else:
            # Ăn quân miễn phí (không bị bắt lại)
            score += target_val * 10 + 200.0
    else:
        if dest_attacked:
            # Đi vào ô bị ngắm mà không ăn quân: mất quân miễn phí
            score -= moving_val * 8.0

    # 4. Bảo vệ quân lớn đang bị ngắm
    if was_attacked and not dest_attacked:
        score += moving_val * 4.0

    # 5. Điểm vị trí và phát triển quân
    if kind == XE:
        # Xuất Xe sớm khỏi góc
        if sr in (0, 9) and sc in (0, 8):
            score += 35.0
        # Xe chiếm lộ thông thoáng hoặc tiến sâu
        if (player == RED and dr <= 4) or (player == BLACK and dr >= 5):
            score += 25.0
    elif kind == MA:
        # Mã nhập trung lộ, kiểm soát các ô tốt
        if 2 <= dc <= 6 and 2 <= dr <= 7:
            score += 20.0
    elif kind == PHAO:
        # Pháo giữ trung lộ hoặc dải hàng 2/7
        if 2 <= dc <= 6:
            score += 15.0
    elif kind == TOT:
        # Tốt vượt sông
        if not crossed_river(sr, player) and crossed_river(dr, player):
            score += 80.0
        # Tốt tiến lên uy hiếp
        if (player == RED and dr < sr) or (player == BLACK and dr > sr):
            score += 15.0

    # Nhiễu ngẫu nhiên nhẹ để đa dạng nước cờ giữa các lựa chọn ngang điểm
    score += random.uniform(0.0, 2.5)
    return score


def get_best_move(game):
    """Lấy nước đi tốt nhất theo chính sách Heuristic / Greedy."""
    moves = game.legal_moves()
    if not moves:
        return None

    best_move = None
    best_score = float('-inf')

    for move in moves:
        s = score_move(game, move)
        if s > best_score:
            best_score = s
            best_move = move

    return best_move


def rollout_policy(game):
    """
    Chính sách chọn nước đi cho bước mô phỏng (Rollout):
    Ưu tiên các nước điểm cao nhất, có xác suất chọn ngẫu nhiên trong top các nước tốt.
    """
    moves = game.legal_moves()
    if not moves:
        return None

    # Tính điểm cho từng nước đi
    scored = [(score_move(game, m), m) for m in moves]
    scored.sort(key=lambda x: x[0], reverse=True)

    # Chọn trong top 3 nước tốt nhất để tạo tính đa dạng khi mô phỏng MCTS
    top_k = scored[:min(3, len(scored))]
    return random.choice(top_k)[1]


def rollout(game, max_steps: int = 40) -> int:
    """
    Thực hiện mô phỏng cờ từ trạng thái hiện tại đến khi kết thúc hoặc đạt giới hạn số bước.
    Trả về: RED, BLACK, hoặc EMPTY (hòa).
    """
    sim_game = game.clone()
    for _ in range(max_steps):
        outcome = sim_game.outcome()
        if outcome is not None:
            return outcome

        move = rollout_policy(sim_game)
        if move is None:
            break
        sim_game = sim_game.play(move)

    outcome = sim_game.outcome()
    return outcome if outcome is not None else EMPTY
