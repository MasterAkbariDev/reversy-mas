"""Serve the local demonstration interface with the Python standard library."""

import argparse
import json
from collections import OrderedDict
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from uuid import uuid4

from ..agents import NAMES, Coordinator, create_agent
from ..environment import BLACK, WHITE, notation
from ..match import Match, Turn
from ..tournament import coordination_experiment, round_robin

STATIC = Path(__file__).with_name("static")
ASSETS = {
    "/": ("index.html", "text/html"),
    "/style.css": ("style.css", "text/css"),
    "/app.js": ("app.js", "text/javascript"),
}


def turn_view(turn: Turn) -> dict:
    decision = turn.decision
    outcome = turn.outcome
    return {
        "actor": turn.actor,
        "color": outcome.before.turn,
        "move": notation(outcome.move),
        "applied": outcome.move,
        "flips": outcome.flips,
        "decision_ms": None if turn.decision_seconds is None else turn.decision_seconds * 1000,
        "reason": decision.reason if decision else "",
        "selected_agent": decision.selected_agent if decision else "",
        "invalid_attempts": turn.invalid_move_attempts,
        "proposals": [
            {
                "sender": exchange.proposal.sender,
                "request_sender": exchange.request.sender,
                "request_recipient": exchange.request.recipient,
                "request_state_id": exchange.request.state_id,
                "state_id": exchange.proposal.state_id,
                "accepted": exchange.accepted,
                "rejection": exchange.rejection,
                "move": notation(exchange.proposal.preferred.move) if exchange.accepted else None,
                "score": exchange.proposal.preferred.score if exchange.accepted else None,
                "reason": exchange.proposal.preferred.reason if exchange.accepted else "",
            }
            for exchange in decision.exchanges
        ] if decision else [],
        "comparison": [
            {"move": notation(item.move), "score": item.score, "supporters": item.supporters}
            for item in decision.comparison
        ] if decision else [],
        "adaptations": [asdict(event) for event in turn.adaptations],
    }


def match_view(identifier: str, match: Match) -> dict:
    position = match.position
    return {
        "id": identifier,
        "board": position.board,
        "state_id": position.identifier,
        "turn": position.turn,
        "legal": position.legal,
        "scores": position.scores,
        "black": match.player_name(BLACK),
        "white": match.player_name(WHITE),
        "human_turn": match.players[position.turn] is None,
        "finished": position.finished,
        "winner": position.winner,
        "history": [turn_view(turn) for turn in match.history],
    }


def integer(value: object, low: int, high: int, label: str) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{label} must be an integer from {low} through {high}")
    return value


class DemoServer(ThreadingHTTPServer):
    def __init__(self, port: int):
        super().__init__(("127.0.0.1", port), Handler)
        self.matches: OrderedDict[str, Match] = OrderedDict()
        self.match_lock = Lock()
        self.tournament_lock = Lock()
        self.authority = f"127.0.0.1:{self.server_port}"

    def new_match(self, request: dict) -> dict:
        mode = request.get("mode")
        black, white = request.get("black"), request.get("white")
        depth = integer(request.get("depth"), 1, 5, "Depth")
        if mode == "human":
            black = "Human"
        elif mode == "team":
            black = Coordinator.name
        elif mode != "ai":
            raise ValueError("Unknown match mode")
        if black not in (*NAMES, "Human") or white not in NAMES or mode == "ai" and black == "Human":
            raise ValueError("Choose supported players")
        match = Match(None if black == "Human" else create_agent(black, depth), create_agent(white, depth))
        identifier = uuid4().hex
        with self.match_lock:
            prior = request.get("prior")
            if isinstance(prior, str):
                self.matches.pop(prior, None)
            self.matches[identifier] = match
            if len(self.matches) > 16:
                self.matches.popitem(last=False)
        return match_view(identifier, match)

    def advance(self, request: dict) -> dict:
        identifier = request.get("id")
        move = request.get("move")
        if move is not None:
            integer(move, 0, 63, "Square")
        with self.match_lock:
            if not isinstance(identifier, str) or identifier not in self.matches:
                raise ValueError("Match has expired. Reset to continue")
            match = self.matches[identifier]
            if request.get("state_id") != match.position.identifier:
                raise ValueError("The board changed. Refresh the match state")
            match.advance(move)
            self.matches.move_to_end(identifier)
            return match_view(identifier, match)


class Handler(BaseHTTPRequestHandler):
    server: DemoServer

    def respond(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; object-src 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def json(self, status: int, value: dict) -> None:
        self.respond(status, "application/json", json.dumps(value).encode("utf-8"))

    def valid_source(self) -> bool:
        local_hosts = (self.server.authority, f"localhost:{self.server.server_port}")
        host = self.headers.get("Host")
        origin = self.headers.get("Origin")
        return host in local_hosts and (origin is None or origin == f"http://{host}")

    def do_GET(self) -> None:
        if not self.valid_source():
            self.json(403, {"error": "Use the local address printed in the terminal"})
        elif self.path in ASSETS:
            filename, content_type = ASSETS[self.path]
            self.respond(200, content_type, (STATIC / filename).read_bytes())
        elif self.path == "/api/options":
            self.json(200, {"agents": NAMES})
        else:
            self.json(404, {"error": "Route not found"})

    def do_POST(self) -> None:
        if not self.valid_source():
            self.json(403, {"error": "Use the local address printed in the terminal"})
            return
        if self.headers.get_content_type() != "application/json":
            self.json(415, {"error": "Expected a JSON request"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 8192:
                raise ValueError("Invalid request size")
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("Expected a JSON object")
            if self.path == "/api/matches":
                result = self.server.new_match(data)
            elif self.path == "/api/turn":
                result = self.server.advance(data)
            elif self.path == "/api/tournament":
                seed = integer(data.get("seed"), -2**31, 2**31 - 1, "Seed")
                openings = integer(data.get("openings"), 1, 10, "Openings")
                depth = integer(data.get("depth"), 1, 3, "Tournament depth")
                if not self.server.tournament_lock.acquire(blocking=False):
                    self.json(409, {"error": "Another tournament is running"})
                    return
                try:
                    result = round_robin(seed, openings, depth)
                    result["coordination_comparison"] = coordination_experiment(result)
                finally:
                    self.server.tournament_lock.release()
            else:
                self.json(404, {"error": "Route not found"})
                return
        except (ValueError, UnicodeDecodeError) as error:
            self.json(400, {"error": str(error)})
            return
        self.json(200, result)

    def log_message(self, format: str, *args: object) -> None:
        """Keep the demo terminal quiet during automatic play."""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    with DemoServer(parser.parse_args().port) as server:
        print(f"REVERSY MAS is running at http://{server.authority}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
