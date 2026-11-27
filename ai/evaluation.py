import math

from game import (
    BLACK, EMPTY, RED, VUA, SI, TUONG, MA, XE, PHAO, TOT, crossed_river,
)

VALUES = {VUA: 0, SI: 200, TUONG: 200, MA: 400, XE: 900, PHAO: 450, TOT: 100}


# chấm điểm cả bàn theo góc nhìn AI
def evaluate_board(game, ai_player):
    if ai_player not in (RED, BLACK):
        raise ValueError("ai_player must be RED or BLACK")

    red_score = 0.0

    for row in range(10):
        for col in range(9):
            piece = game.board[row][col]
            if piece == EMPTY:
                continue

            if piece > 0:
                owner = RED
            else:
                owner = BLACK

            kind = abs(piece)  # xác định loại quân (VUA, SI, TUONG,..)
            piece_score = VALUES[kind] # điểm số tương ứng với loại quân

            if kind == TOT:
                if owner == RED:
                    advance = 9 - row
                else:
                    advance = row

                piece_score += 10 * advance
                if crossed_river(row, owner):
                    piece_score += 80
                    piece_score += 5 * (4 - abs(col - 4))

            elif kind in (MA, XE, PHAO):
                piece_score += 5 * (4 - abs(col - 4))

            if owner == RED:
                red_score += piece_score
            else:
                red_score -= piece_score

    
    if game.in_check(RED):
        red_score -= 50
    if game.in_check(BLACK):
        red_score += 50

    if ai_player == RED:
        return red_score
    return -red_score


# ưu tiên bắt quân giá trị cao bằng quân giá trị thấp
def score_move(game, move):
    source_row, source_col = move.src
    target_row, target_col = move.dst
    attacker = abs(game.board[source_row][source_col])
    victim = abs(game.board[target_row][target_col])

    if victim == EMPTY:
        return -10_000

    return 10 * VALUES[victim] - VALUES[attacker]

