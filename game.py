from dataclasses import dataclass

RED, BLACK, EMPTY = 1, -1, 0
VUA, SI, TUONG, MA, XE, PHAO, TOT = range(1, 8)
DIRECTIONS = ((1, 0), (-1, 0), (0, 1), (0, -1))


@dataclass(frozen=True, order=True)
class Move:
    src: tuple[int, int]  # ô nguồn
    dst: tuple[int, int]  # ô đích

def inside(row, col):
    return 0 <= row < 10 and 0 <= col < 9

def palace(row, col, player):
    return 3 <= col <= 5 and (7 <= row <= 9 if player == RED else 0 <= row <= 2)

def crossed_river(row, player):
    return row <= 4 if player == RED else row >= 5


class CoTuongGame:
    def __init__(self, board=None, current_player=RED):
        if current_player not in (RED, BLACK):
            raise ValueError("current_player must be RED or BLACK")
        if board is None:
            board = [[EMPTY] * 9 for _ in range(10)]
            back = (XE, MA, TUONG, SI, VUA, SI, TUONG, MA, XE)
            board[0] = [-piece for piece in back]
            board[9] = list(back)
            for row, player in ((2, BLACK), (7, RED)):
                for col in (1, 7):
                    board[row][col] = player * PHAO
            for row, player in ((3, BLACK), (6, RED)):
                for col in range(0, 9, 2):
                    board[row][col] = player * TOT
        if len(board) != 10:
            raise ValueError("The board must have 10 rows and 9 columns")
        for row in board:
            if len(row) != 9:
                raise ValueError("The board must have 10 rows and 9 columns")

        for row in board:
            for piece in row:
                if type(piece) is not int:
                    raise ValueError("Piece codes must be integers in [-7, 7]")
                if abs(piece) > TOT:
                    raise ValueError("Piece codes must be integers in [-7, 7]")
                
        self.board = []
        for row in board:
            copied_row = row.copy()
            self.board.append(copied_row)
        self.current_player = current_player
        self.history = (self.key(),)

    # lưu vị trí quân và bên đến lượt để nhận diện trạng thái lặp
    def key(self):
        pieces = []
        for row in self.board:
            for piece in row:
                pieces.append(piece)

        board_tuple = tuple(pieces)
        current_player = self.current_player
        state_key = (board_tuple, current_player)
        return state_key

    def clone(self):
        other = object.__new__(CoTuongGame)
        other.board = []
        for row in self.board:
            copied_row = row.copy()
            other.board.append(copied_row)
        other.current_player = self.current_player
        other.history = self.history
        return other

    # tạo trạng thái sau nước đi trên bản clone (chưa kiểm tra hợp lệ)
    def _after(self, move):
        child = self.clone()
        row, col = move.src
        nr, nc = move.dst
        child.board[nr][nc] = child.board[row][col]
        child.board[row][col] = EMPTY
        child.current_player = -self.current_player
        child.history += (child.key(),)
        return child

    # kiểm tra nước đi rồi trả trạng thái mới
    def play(self, move):
        moves = self.legal_moves()
        if self.outcome(moves) is not None or move not in moves:
            raise ValueError(f"Illegal move: {move}")
        return self._after(move)

    # tìm tọa độ tướng
    def king_square(self, player):
        target_piece = player * VUA

        for row in range(10):
            for col in range(9):
                if self.board[row][col] == target_piece:
                    return (row, col)
        return None

    # sinh nước đúng cách đi từng quân
    def pseudo_moves(self, player):
        for row in range(10):
            for col in range(9):
                piece = self.board[row][col]
                if piece * player <= 0:
                    continue
                kind = abs(piece)
                targets = []
                if kind in (XE, PHAO):
                    for dr, dc in DIRECTIONS:
                        nr, nc = row + dr, col + dc
                        screen = False  
                        while inside(nr, nc):
                            target = self.board[nr][nc]
                            if kind == XE:
                                if target * player <= 0:
                                    targets.append((nr, nc))
                                if target:
                                    break
                            elif not screen:
                                if not target:
                                    targets.append((nr, nc))
                                else:
                                    screen = True
                            elif target:
    
                                if target * player < 0:
                                    targets.append((nr, nc))
                                break
                            nr, nc = nr + dr, nc + dc
                elif kind == MA:
                    for dr, dc in ((2, 1), (2, -1), (-2, 1), (-2, -1),(1, 2), (-1, 2), (1, -2), (-1, -2)):
                        lr = row + (dr // 2 if abs(dr) == 2 else 0)
                        lc = col + (dc // 2 if abs(dc) == 2 else 0)
                        if inside(row + dr, col + dc) and not self.board[lr][lc]:
                            targets.append((row + dr, col + dc))
                elif kind == TUONG:
                    for dr, dc in ((2, 2), (2, -2), (-2, 2), (-2, -2)):
                        nr, nc = row + dr, col + dc
                        if (inside(nr, nc) and not crossed_river(nr, player)
                                and not self.board[row + dr // 2][col + dc // 2]):
                            targets.append((nr, nc))
                elif kind == SI:
                    targets = [(row + dr, col + dc)
                               for dr, dc in ((1, 1), (1, -1), (-1, 1), (-1, -1))
                               if palace(row + dr, col + dc, player)]
                elif kind == VUA:
                    targets = [(row + dr, col + dc) for dr, dc in DIRECTIONS
                               if palace(row + dr, col + dc, player)]
                    for dr in (-1, 1):
                        nr = row + dr
                        while inside(nr, col):
                            if self.board[nr][col]:
                                if self.board[nr][col] == -player * VUA:
                                    targets.append((nr, col))
                                break
                            nr += dr
                elif kind == TOT:
                    targets = [(row - player, col)]
                    if crossed_river(row, player):
                        targets.extend(((row, col - 1), (row, col + 1)))
                for nr, nc in targets:
                    if inside(nr, nc) and self.board[nr][nc] * player <= 0:
                        yield Move((row, col), (nr, nc))

    # kiểm tra tướng có đang bị chiêu không
    def in_check(self, player):
        king = self.king_square(player)
        if king is None:
            return True

        opponent = -player
        for move in self.pseudo_moves(opponent):
            if move.dst == king:
                return True

        return False

    def legal_moves(self):
        if self.king_square(RED) is None or self.king_square(BLACK) is None:
            return []
        player = self.current_player
        valid_moves = []

        for move in self.pseudo_moves(player):
            target_row, target_col = move.dst
            target_piece = self.board[target_row][target_col]

            if abs(target_piece) == VUA:
                continue
            next_game = self._after(move)
          
            if next_game.in_check(player):
                continue

            valid_moves.append(move)

        return valid_moves

    # trả kết quả: None nếu chưa kết thúc, RED/BLACK là bên thắng, EMPTY là hòa
    def outcome(self, moves=None):
        for player in (RED, BLACK):
            if self.king_square(player) is None:
                return -player
        if moves is None:
            moves = self.legal_moves()
        # hết nước đi là thua kể cả khi không bị chiếu
        if not moves:
            return -self.current_player
        if self.history.count(self.key()) >= 3:
            return EMPTY
        return None
