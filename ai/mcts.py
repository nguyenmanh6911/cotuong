
import math
import random
import time

from game import EMPTY
from ai.rollout import rollout


class Node:
    def __init__(self, game, parent=None, move=None):
        self.game = game
        self.parent = parent
        self.move = move
        self.children = []
        self.moves = game.legal_moves()
        self.outcome = game.outcome(self.moves)  # None nếu chưa kết thúc
        self.untried = list(self.moves) if self.outcome is None else []
        random.shuffle(self.untried)
        self.N = 0
        self.W = 0.0 

    def uct(self, c):
        return (self.W / self.N
                + c * math.sqrt(math.log(self.parent.N) / self.N))


def mcts_best_move(game, iterations=300, time_limit=None, c=1.41):
    root = Node(game)
    if not root.moves:
        return None
    if len(root.moves) == 1:
        return root.moves[0]

    deadline = None if time_limit is None else time.perf_counter() + time_limit
    i = 0
    while i < iterations if deadline is None else time.perf_counter() < deadline:
        i += 1
        # 1. Selection
        node = root
        while not node.untried and node.children:
            node = max(node.children, key=lambda ch: ch.uct(c))

        # 2. Expansion
        if node.untried:
            move = node.untried.pop()
            child = Node(node.game._after(move), node, move)
            node.children.append(child)
            node = child

        # 3. Simulation
        result = node.outcome if node.outcome is not None else rollout(node.game)

        # 4. Backpropagation
        while node is not None:
            node.N += 1
            mover = -node.game.current_player
            node.W += 0.5 if result == EMPTY else (1.0 if result == mover else 0.0)
            node = node.parent

    for ch in root.children:
        if ch.outcome == game.current_player:
            return ch.move
    return max(root.children, key=lambda ch: ch.N).move