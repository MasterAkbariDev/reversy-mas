"""Strategic, greedy, and defensive policies and shared Reversi features."""

from math import inf

from .base import Strategy
from ..environment import Board, Color, CORNERS, Move, Position, flips, legal_moves, opponent, play
from ..messages import Rating

# Directional neighbors of the four corners, with diagonals marked separately.
NEAR_CORNERS = (
    (0, (1, 8), 9), (7, (6, 15), 14),
    (56, (48, 57), 49), (63, (55, 62), 54),
)
EDGES = frozenset(index for index in range(64) if 0 in divmod(index, 8) or 7 in divmod(index, 8))
# Symmetric positional preferences inspired by the original REVERSY evaluator.
POSITION = (
    90, -8, 12, 6, 6, 12, -8, 90,
    -8, -16, -3, -2, -2, -3, -16, -8,
    12, -3, 7, 3, 3, 7, -3, 12,
    6, -2, 3, 1, 1, 3, -2, 6,
    6, -2, 3, 1, 1, 3, -2, 6,
    12, -3, 7, 3, 3, 7, -3, 12,
    -8, -16, -3, -2, -2, -3, -16, -8,
    90, -8, 12, 6, 6, 12, -8, 90,
)


def corner_risk(board: Board, color: Color) -> int:
    return sum(
        14 * sum(board[edge] == color for edge in edges) + 26 * (board[diagonal] == color)
        for corner, edges, diagonal in NEAR_CORNERS if board[corner] == 0
    )


def stable_edges(board: Board, color: Color) -> int:
    """Count corner-connected same-color edge runs, a lower bound on stability."""
    stable = set()
    for corner, horizontal, vertical in ((0, 1, 8), (7, -1, 8), (56, 1, -8), (63, -1, -8)):
        if board[corner] != color:
            continue
        stable.add(corner)
        for stride in (horizontal, vertical):
            for distance in range(1, 8):
                square = corner + stride * distance
                if board[square] != color:
                    break
                stable.add(square)
    return len(stable)


def evaluate(board: Board, color: Color, mobility: int) -> int:
    foe = opponent(color)
    empties = board.count(0)
    disc_weight = 12 if empties <= 12 else 1
    return (
        color * sum(value * weight for value, weight in zip(board, POSITION))
        + 10 * mobility
        + corner_risk(board, foe) - corner_risk(board, color)
        + disc_weight * (board.count(color) - board.count(foe))
    )


def search(position: Position, depth: int, alpha: float, beta: float, root: Color) -> float:
    board, turn = position.board, position.turn
    ours = legal_moves(board, root)
    theirs = legal_moves(board, opponent(root))
    if not ours and not theirs:
        difference = board.count(root) - board.count(opponent(root))
        if difference == 0:
            return 0
        return difference + (100_000 if difference > 0 else -100_000)
    if depth == 0:
        return evaluate(board, root, len(ours) - len(theirs))

    maximizing = turn == root
    moves = ours if maximizing else theirs
    if not moves:
        return search(Position(board, opponent(turn)), depth, alpha, beta, root)

    best = -inf if maximizing else inf
    for move in sorted(moves, key=POSITION.__getitem__, reverse=True):
        child = Position(play(board, turn, move), opponent(turn))
        score = search(child, depth - 1, alpha, beta, root)
        if maximizing:
            best = max(best, score)
            alpha = max(alpha, best)
        else:
            best = min(best, score)
            beta = min(beta, best)
        if alpha >= beta:
            break
    return best


class Strategic(Strategy):
    name = "Strategic"

    def __init__(self, depth: int = 2, exact_endgame: int = 5):
        if not 1 <= depth <= 5 or not 0 <= exact_endgame <= 8:
            raise ValueError("Use search depth 1–5 and exact endgame threshold 0–8")
        self.depth = depth
        self.exact_endgame = exact_endgame

    def rate(self, position: Position) -> tuple[Rating, ...]:
        board, color = position.board, position.turn
        empties = board.count(0)
        depth = empties if empties <= self.exact_endgame else self.depth
        ratings = []
        for move in position.legal:
            child = Position(play(board, color, move), opponent(color))
            # A full root window makes every reported move score exact for this search depth.
            score = search(child, depth - 1, -inf, inf, color)
            ratings.append(Rating(move, score, f"Alpha-beta, depth {depth}, evaluation {score:g}."))
        return tuple(ratings)


class Greedy(Strategy):
    name = "Greedy"

    def __init__(self, corner_bonus: int = 0):
        self.corner_bonus = corner_bonus

    def rate(self, position: Position) -> tuple[Rating, ...]:
        ratings = []
        for move in position.legal:
            count = len(flips(position.board, position.turn, move))
            bonus = self.corner_bonus if move in CORNERS else 0
            ratings.append(Rating(move, count + bonus, f"Flips {count} discs with corner bonus {bonus}."))
        return tuple(ratings)


class Defensive(Strategy):
    name = "Defensive"

    def rate(self, position: Position) -> tuple[Rating, ...]:
        color = position.turn
        foe = opponent(color)
        ratings = []
        for move in position.legal:
            board = play(position.board, color, move)
            replies = legal_moves(board, foe)
            exposed = sum(reply in CORNERS for reply in replies)
            stable = stable_edges(board, color) - stable_edges(board, foe)
            risk = corner_risk(board, color) - corner_risk(board, foe)
            score = 45 * (move in CORNERS) + 8 * stable - 7 * len(replies) - 35 * exposed - risk
            reason = f"Opponent replies {len(replies)}, exposed corners {exposed}, stable edge lead {stable}, risk {risk}."
            ratings.append(Rating(move, score, reason))
        return tuple(ratings)
