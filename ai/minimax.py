import time

from dataclasses import dataclass, field
from ai.evaluation import evaluate_board, score_move



@dataclass
class SearchResult:
    move: object
    nodes: int
    seconds: float
    score: float | None = None
    visits: dict = field(default_factory=dict)


INF = float("inf")
WIN_SCORE = 1_000_000


# lấy nước ưu tiên trước để Alpha-beta có thể cắt nhiều nhánh hơn
def ordered_moves(game, moves, use_ordering=True):
    if not use_ordering:
        return list(moves)

    def priority(move):
        return score_move(game, move)

    return sorted(moves, key=priority, reverse=True)


# tìm điểm tốt nhất (AI lấy MAX, đối thủ lấy MIN)
def minimax(game, depth, alpha, beta, ai_player, stats=None,use_pruning=True, use_ordering=True, quiescence_depth=0, ply=0):
    if stats is not None:
        stats["nodes"] += 1

    moves = game.legal_moves()
    winner = game.outcome(moves)

    if winner is not None:
        if winner == 0:
            return 0
        if winner == ai_player:
            return WIN_SCORE - ply
        return -WIN_SCORE + ply

    maximizing = game.current_player == ai_player
    if maximizing:
        best_score = -INF
    else:
        best_score = INF

    if depth <= 0:
        static_score = evaluate_board(game, ai_player)
        if quiescence_depth == 0:
            return static_score

        # Mở rộng ngắn ở lá để tránh bắt quân rồi bị bắt lại ngay sau đó
        if not game.in_check(game.current_player):
            best_score = static_score
            if maximizing:
                if use_pruning and static_score >= beta:
                    return static_score
                alpha = max(alpha, static_score)
            else:
                if use_pruning and static_score <= alpha:
                    return static_score
                beta = min(beta, static_score)

            captures = []
            for move in moves:
                target_row, target_col = move.dst
                if game.board[target_row][target_col] != 0:
                    captures.append(move)
            moves = captures
        # Nếu đang bị chiếu, giữ mọi nước giải chiếu thay vì chỉ xét bắt quân.

    for move in ordered_moves(game, moves, use_ordering):
        next_game = game._after(move)
        next_quiescence_depth = quiescence_depth
        if depth <= 0:
            next_quiescence_depth -= 1

        score = minimax(
            next_game, depth - 1, alpha, beta, ai_player, stats,
            use_pruning, use_ordering, next_quiescence_depth, ply + 1,
        )

        if maximizing:
            best_score = max(best_score, score)
            alpha = max(alpha, best_score)
        else:
            best_score = min(best_score, score)
            beta = min(beta, best_score)

        if use_pruning and alpha >= beta:
            break

    return best_score


# Chọn nước tốt nhất; tùy chọn trả kèm điểm, số nút và thời gian.
def find_best_move(game, depth=2, use_pruning=True, return_stats=False, use_ordering=True, quiescence_depth=0):
    if type(depth) is not int or depth < 1:
        raise ValueError("depth must be a positive integer")
    if type(quiescence_depth) is not int or quiescence_depth < 0:
        raise ValueError("quiescence_depth must be a nonnegative integer")

    start = time.perf_counter()
    stats = {"nodes": 0}
    ai_player = game.current_player
    moves = game.legal_moves()
    winner = game.outcome(moves)
    best_move = None
    best_score = -INF
    alpha = -INF
    beta = INF

    if winner is not None:
        if winner == 0:
            best_score = 0
        elif winner == ai_player:
            best_score = WIN_SCORE
        else:
            best_score = -WIN_SCORE
    else:
        for move in ordered_moves(game, moves, use_ordering):
            next_game = game._after(move)
            score = minimax(
                next_game, depth - 1, alpha, beta, ai_player, stats,
                use_pruning, use_ordering, quiescence_depth, 1,
            )

            if best_move is None or score > best_score:
                best_move = move
                best_score = score
            alpha = max(alpha, best_score)

    if not return_stats:
        return best_move

    return {
        "move": best_move,
        "score": best_score,
        "nodes": stats["nodes"],
        "time": time.perf_counter() - start,
        "depth": depth,
        "pruning": use_pruning,
        "ordering": use_ordering,
        "quiescence_depth": quiescence_depth,
    }

