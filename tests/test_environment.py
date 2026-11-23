import random
from dataclasses import FrozenInstanceError

import pytest

from reversy_mas.environment import BLACK, WHITE, Game, Position, flips, legal_moves, play


def test_initial_position_and_snapshot():
    game = Game()
    before = game.position
    assert before.scores == (2, 2)
    assert before.turn == BLACK
    assert before.board[27:29] == (WHITE, BLACK)
    assert before.board[35:37] == (BLACK, WHITE)
    assert before.legal == (19, 26, 37, 44)
    assert before.winner is None
    with pytest.raises(FrozenInstanceError):
        before.turn = WHITE
    after = game.submit(19)
    assert after.turn == WHITE
    assert after.scores == (4, 1)
    assert after.identifier != before.identifier
    assert before.scores == (2, 2)


@pytest.mark.parametrize("move", [None, -1, 64, True, 19.0, 0, 27])
def test_reject_illegal_actions_without_mutation(move):
    game = Game()
    original = game.position
    with pytest.raises(ValueError):
        game.submit(move)
    assert game.position is original


def test_flip_all_eight_directions_in_one_move():
    cells = [0] * 64
    adjacent = (18, 19, 20, 26, 28, 34, 35, 36)
    for square in adjacent:
        cells[square] = WHITE
    for square in (9, 11, 13, 25, 29, 41, 43, 45):
        cells[square] = BLACK
    board = tuple(cells)
    assert set(flips(board, BLACK, 27)) == set(adjacent)
    played = play(board, BLACK, 27)
    assert played.count(BLACK) == 17
    assert played.count(WHITE) == 0


def test_no_wrap_at_edge():
    cells = [0] * 64
    cells[7], cells[6] = WHITE, BLACK
    assert not flips(tuple(cells), BLACK, 8)


def test_forced_pass_then_winner():
    start = Position((0, BLACK, WHITE) + (WHITE,) * 61, BLACK)
    game = Game(start)
    assert not start.legal and not start.finished
    after = game.submit(None)
    assert after.board == start.board
    assert after.identifier != start.identifier
    assert after.legal == (0,)
    end = game.submit(0)
    assert end.finished and end.winner == WHITE
    assert end.scores == (0, 64)
    with pytest.raises(ValueError):
        game.submit(None)


@pytest.mark.parametrize("board, winner", [
    ((BLACK,) * 20 + (0,) * 44, BLACK),
    ((WHITE,) * 64, WHITE),
    ((BLACK,) * 32 + (WHITE,) * 32, 0),
])
def test_terminal_winner_even_with_empty_squares(board, winner):
    position = Position(board)
    assert position.finished
    assert position.winner == winner


def reference_flips(board, color, move):
    """Direct row/column implementation independent of the production ray table."""
    if board[move] != 0:
        return set()
    result = set()
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == dc == 0:
                continue
            row, col = divmod(move, 8)
            row, col = row + dr, col + dc
            path = []
            while 0 <= row < 8 and 0 <= col < 8:
                square = row * 8 + col
                if board[square] == color:
                    result.update(path)
                    break
                if board[square] == 0:
                    break
                path.append(square)
                row, col = row + dr, col + dc
    return result


def test_seeded_full_game_against_reference_rules():
    rng = random.Random(186)
    game = Game()
    while not game.position.finished:
        position = game.position
        expected = {
            move: captured for move in range(64)
            if (captured := reference_flips(position.board, position.turn, move))
        }
        assert set(expected) == set(position.legal)
        if not expected:
            game.submit(None)
            continue
        move = rng.choice(list(expected))
        assert set(flips(position.board, position.turn, move)) == expected[move]
        after = game.submit(move)
        assert after.board.count(0) == position.board.count(0) - 1
        assert set(legal_moves(after.board, after.turn)).issubset(
            index for index, cell in enumerate(after.board) if cell == 0
        )
