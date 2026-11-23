import json
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from reversy_mas.ui.app import DemoServer


@pytest.fixture
def app():
    with DemoServer(0) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        yield f"http://{server.authority}"
        server.shutdown()
        thread.join()


def post(app, path, values):
    request = Request(app + path, json.dumps(values).encode(), {"Content-Type": "application/json"})
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def test_serves_app_and_steps_team_match(app):
    with urlopen(app, timeout=5) as response:
        assert b'id="board"' in response.read()
    with urlopen(app + "/app.js", timeout=5) as response:
        assert response.headers.get_content_type() == "text/javascript"
    match = post(app, "/api/matches", {"mode": "team", "white": "Greedy", "depth": 1})
    turn = {"id": match["id"], "state_id": match["state_id"], "move": None}
    after = post(app, "/api/turn", turn)
    entry = after["history"][0]
    assert after["scores"] == [4, 1] and len(entry["proposals"]) == 4
    assert all(proposal["request_state_id"] == proposal["state_id"] == match["state_id"] for proposal in entry["proposals"])
    assert entry["applied"] in match["legal"]
    with pytest.raises(HTTPError) as error:
        post(app, "/api/turn", turn)
    assert error.value.code == 400


def test_real_local_tournament_endpoint(app):
    report = post(app, "/api/tournament", {"seed": 7, "openings": 1, "depth": 1})
    assert report["total_matches"] == 20 and len(report["coordination_comparison"]) == 4
