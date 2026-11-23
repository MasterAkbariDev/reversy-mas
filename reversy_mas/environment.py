"""Pure Reversi rules and the match's authoritative state transition."""

from dataclasses import dataclass, field
from functools import lru_cache
from hashlib import sha256
from typing import Literal

Color = Literal[1, -1]
Move = int
Board = tuple[int, ...]
BLACK, WHITE = 1, -1
CORNERS = (0, 7, 56, 63)
DIRECTIONS = tuple(
    (dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc
)


def _rays(square: Move) -> tuple[tuple[Move, ...], ...]:
    row, col = divmod(square, 8)
    return tuple(
        tuple(
            (row + step * dr) * 8 + col + step * dc
            for step in range(1, 8)
            if 0 <= row + step * dr < 8 and 0 <= col + step * dc < 8
        )
        for dr, dc in DIRECTIONS
    )


RAYS = tuple(_rays(square) for square in range(64))


def initial_board() -> Board:
    cells = [0] * 64
    cells[27] = cells[36] = WHITE
    cells[28] = cells[35] = BLACK
    return tuple(cells)


def opponent(color: Color) -> Color:
    return WHITE if color == BLACK else BLACK


def notation(move: Move | None) -> str:
    if move is None:
        return "Pass"
    row, col = divmod(move, 8)
    return f"{chr(65 + col)}{row + 1}"


def flips(board: Board, color: Color, move: Move) -> tuple[Move, ...]:
    if type(move) is not int or not 0 <= move < 64 or board[move]:
        return ()
    captured = []
    foe = opponent(color)
    for ray in RAYS[move]:
        line = []
        for square in ray:
            value = board[square]
            if value == foe:
                line.append(square)
                continue
            if value == color:
                captured.extend(line)
            break
    return tuple(captured)


@lru_cache(maxsize=32_768)
def legal_moves(board: Board, color: Color) -> tuple[Move, ...]:
    return tuple(
        move for move, value in enumerate(board)
        if value == 0 and flips(board, color, move)
    )


def play(board: Board, color: Color, move: Move) -> Board:
    captured = flips(board, color, move)
    if not captured:
        raise ValueError("Illegal move")
    cells = list(board)
    cells[move] = color
    for square in captured:
        cells[square] = color
    return tuple(cells)


def terminal(board: Board) -> bool:
    return not legal_moves(board, BLACK) and not legal_moves(board, WHITE)


@dataclass(frozen=True)
class Position:
    board: Board = field(default_factory=initial_board)
    turn: Color = BLACK

    @property
    def identifier(self) -> str:
        cells = bytes(value + 1 for value in (*self.board, self.turn))
        return sha256(cells).hexdigest()

    @property
    def legal(self) -> tuple[Move, ...]:
        return legal_moves(self.board, self.turn)

    @property
    def finished(self) -> bool:
        return terminal(self.board)

    @property
    def scores(self) -> tuple[int, int]:
        return self.board.count(BLACK), self.board.count(WHITE)

    @property
    def winner(self) -> Color | Literal[0] | None:
        if not self.finished:
            return None
        black, white = self.scores
        if black == white:
            return 0
        return BLACK if black > white else WHITE


class Game:
    def __init__(self, position: Position | None = None):
        self._position = position or Position()

    @property
    def position(self) -> Position:
        return self._position

    def submit(self, move: Move | None) -> Position:
        before = self.position
        if before.finished:
            raise ValueError("Match has finished")
        if move is None:
            if before.legal:
                raise ValueError("Passing is legal only with no legal moves")
            board = before.board
        else:
            board = play(before.board, before.turn, move)
        self._position = Position(board, opponent(before.turn))
        return self._position
