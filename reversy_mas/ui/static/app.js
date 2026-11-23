"use strict";

const $ = (id) => document.getElementById(id);
const matchControls = ["mode", "black-agent", "white-agent", "depth", "reset"];
let match;
let running = false;
let busy = false;
let timer;
const squares = [];

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

async function api(path, data) {
  const response = await fetch(path, data === undefined ? {} : {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(data),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "The request failed.");
  return payload;
}

function setError(error) {
  $("match-error").hidden = !error;
  $("match-error").textContent = error?.message || "";
}

function coordinate(index) {
  return String.fromCharCode(65 + index % 8) + (1 + Math.floor(index / 8));
}

function canAutoPlay() {
  return match && !match.finished && (!match.human_turn || !match.legal.length);
}

function controls() {
  for (const id of matchControls) $(id).disabled = busy;
  $("black-agent").disabled = busy || $("mode").value !== "ai";
  $("start").disabled = busy || running || !canAutoPlay();
  $("pause").disabled = !running;
  $("step").disabled = busy || running || !canAutoPlay();
  $("pass").hidden = !(match?.human_turn && !match.finished && !match.legal.length);
  $("pass").disabled = busy || running;
  squares.forEach((button, index) => {
    button.disabled = !(match?.human_turn && !busy && !match.finished && match.legal.includes(index));
  });
}

function applyMode() {
  const mode = $("mode").value;
  $("black-agent").value = mode === "human" ? "Human"
    : mode === "team" ? "Coordinator Team" : "Strategic";
  $("black-agent").querySelector('[value="Human"]').hidden = mode !== "human";
  controls();
}

function stop() {
  running = false;
  clearTimeout(timer);
  controls();
}

function schedule() {
  if (running && canAutoPlay() && !busy) {
    timer = setTimeout(() => advance(null), 280);
  } else {
    stop();
  }
}

async function advance(move) {
  if (busy || !match) return;
  busy = true;
  setError();
  controls();
  try {
    match = await api("/api/turn", {id: match.id, state_id: match.state_id, move});
    render();
  } catch (error) {
    setError(error);
    stop();
  } finally {
    busy = false;
    controls();
    schedule();
  }
}

async function reset() {
  if (busy) return;
  stop();
  setError();
  busy = true;
  controls();
  try {
    match = await api("/api/matches", {
      mode: $("mode").value, black: $("black-agent").value, white: $("white-agent").value,
      depth: $("depth").valueAsNumber, prior: match?.id,
    });
    render();
  } catch (error) {
    setError(error);
  } finally {
    busy = false;
    controls();
  }
}

function render() {
  const last = match.history.at(-1);
  squares.forEach((button, index) => {
    const value = match.board[index];
    const legal = match.legal.includes(index);
    const description = value === 1 ? "black disc" : value === -1 ? "white disc" : legal ? "legal move" : "empty";
    button.setAttribute("aria-label", coordinate(index) + ", " + description);
    button.classList.toggle("last", last?.applied === index);
    button.replaceChildren();
    if (value) button.append(element("span", undefined, "disc " + (value === 1 ? "black" : "white")));
    else if (legal) button.append(element("span", undefined, "hint"));
  });
  $("black-player").textContent = match.black;
  $("white-player").textContent = match.white;
  $("black-score").textContent = match.scores[0];
  $("white-score").textContent = match.scores[1];
  const color = match.turn === 1 ? "Black" : "White";
  const player = match.turn === 1 ? match.black : match.white;
  const winner = match.winner === 1 ? "Black · " + match.black : "White · " + match.white;
  $("status").textContent = match.finished ? (match.winner === 0 ? "Match over · draw" : "Winner · " + winner)
    : match.legal.length ? color + " to move · " + player : color + " has no legal moves · pass";
  const history = $("history-select");
  const descriptions = match.history.map((entry, i) =>
    (i + 1) + ". " + (entry.color === 1 ? "Black" : "White") + " · " + entry.actor + " · " + entry.move
  );
  history.replaceChildren(...descriptions.map((description, index) => new Option(description, index)));
  history.disabled = !descriptions.length;
  history.value = String(descriptions.length - 1);
  $("moves").replaceChildren(...descriptions.map((description) =>
    element("li", description.replace(/^\d+\. /, ""))
  ));
  $("history-count").textContent = descriptions.length + (descriptions.length === 1 ? " turn" : " turns");
  inspect();
}

function disclosure(title, children) {
  const block = element("details");
  block.append(element("summary", title), ...children);
  return block;
}

function inspect() {
  const output = $("inspector");
  const turn = match?.history[$("history-select").value];
  output.replaceChildren();
  if (!turn) {
    output.append(element("p", "Play a turn to see the decision and feedback.", "muted"));
    return;
  }
  const detail = turn.reason || (turn.move === "Pass" ? "No legal moves. The environment passed the turn."
    : "The environment validated the human move.");
  output.append(element("p", detail));
  if (turn.decision_ms !== null) {
    output.append(element("small", turn.decision_ms.toFixed(2) + " ms · " + turn.flips + " flips"));
  }
  if (turn.proposals.length) {
    const messages = element("ul", undefined, "messages");
    turn.proposals.forEach((proposal) => {
      const line = element("li");
      line.append(element("strong", proposal.request_sender + " → " + proposal.request_recipient));
      line.append(element("div", proposal.sender + " replied · " + (proposal.accepted
        ? proposal.move + " · raw score " + Number(proposal.score.toFixed(2)) : proposal.rejection)));
      if (proposal.reason) line.append(element("div", proposal.reason, "muted"));
      if (!proposal.accepted) line.append(element("div", "Reply state " + proposal.state_id, "state-id muted"));
      messages.append(line);
    });
    const results = element("ul", undefined, "messages");
    turn.comparison.forEach((entry) => results.append(element("li",
      entry.move + " · " + entry.score.toFixed(3) + " · " + entry.supporters.join(", "))));
    const state = element("p", "Request state " + turn.proposals[0].request_state_id, "state-id muted");
    const communication = disclosure("Team messages (" + turn.proposals.length + ")", [state, messages, results]);
    communication.open = true;
    output.append(element("p", "Selected strategy · " + turn.selected_agent), communication);
  }
  if (turn.adaptations.length) {
    const entries = element("ul", undefined, "messages");
    turn.adaptations.forEach((event) => entries.append(element("li",
      event.agent + " · " + event.feature + " " + event.previous_weight.toFixed(3) + " → "
      + event.new_weight.toFixed(3) + ". " + event.reason)));
    const updates = disclosure("Adaptive updates (" + turn.adaptations.length + ")", [entries]);
    updates.open = true;
    output.append(updates);
  }
}

function table(headers, rows) {
  const wrap = element("div", undefined, "table-wrap");
  const node = element("table");
  const head = node.createTHead().insertRow();
  headers.forEach((header) => head.append(element("th", header)));
  const body = node.createTBody();
  rows.forEach((data) => {
    const row = body.insertRow();
    data.forEach((value) => row.insertCell().textContent = value);
  });
  wrap.append(node);
  return wrap;
}

function section(title, ...children) {
  const panel = element("section", undefined, "panel");
  panel.append(element("h2", title), ...children);
  return panel;
}

function chart(rows, max, format) {
  const node = element("div");
  for (const [name, value] of rows) {
    const bar = element("progress");
    bar.max = max;
    bar.value = value;
    bar.setAttribute("aria-label", name);
    const row = element("div", undefined, "chart-row");
    row.append(element("span", name), bar, element("span", format(value)));
    node.append(row);
  }
  return node;
}

function percent(value) {
  return (value * 100).toFixed(1) + "%";
}

function tournamentResults(report) {
  const agents = Object.entries(report.agents);
  const counts = (data) => Object.entries(data).map(([key, count]) => key + " " + count).join(" · ") || "—";
  const changes = (row) => counts(Object.fromEntries(Object.entries(row.adaptation_updates).map(([key, count]) =>
    [key, count + " (Δ " + row.mean_absolute_weight_change[key].toFixed(3) + ")"])));
  const chartRows = agents.map(([name, row]) => [name, row.average_decision_ms]);
  $("tournament-results").replaceChildren(
    section("Win rate", chart(agents.map(([name, row]) => [name, row.win_rate]), 1, percent)),
    section("Mean decision time", chart(chartRows, Math.max(1, ...chartRows.map(([, value]) => value)),
      (value) => value.toFixed(2) + " ms")),
    section("Agent results", table(
      ["Agent", "Matches", "W", "L", "D", "Mean match (s)", "Invalid moves", "Selections", "Updates (mean |Δ|)"],
      agents.map(([name, row]) => [name, row.matches, row.wins, row.losses, row.draws,
        row.average_match_seconds.toFixed(3), row.invalid_attempts, counts(row.selection_counts), changes(row)])
    )),
    section("Coordination experiment", element("p",
      "Each comparison uses the same opponent, opening, and color. Wins earn 1 point, draws ½.", "muted"), table(
      ["Solo agent", "Paired fixtures", "Team points", "Solo points", "Point-rate difference"],
      report.coordination_comparison.map((row) => [
        row.individual, row.fixtures, row.team, row.solo, percent(row.point_rate_delta)
      ])
    )),
    section("Match results", disclosure("Show all " + report.total_matches + " matches", [table(
      ["Opening", "Black", "White", "Score", "Winner", "Turns"],
      report.matches.map((row) => [row.opening, row.black, row.white, row.black_score + "–" + row.white_score,
        row.winner, row.turns])
    )]))
  );
}

function showPage(tournament) {
  stop();
  $("match-page").hidden = tournament;
  $("tournament-page").hidden = !tournament;
  $("show-match").classList.toggle("active", !tournament);
  $("show-tournament").classList.toggle("active", tournament);
  $("show-match").setAttribute("aria-pressed", String(!tournament));
  $("show-tournament").setAttribute("aria-pressed", String(tournament));
}

$("settings").addEventListener("submit", (event) => { event.preventDefault(); reset(); });
$("mode").addEventListener("change", applyMode);
$("history-select").addEventListener("change", inspect);
$("start").addEventListener("click", () => { running = true; controls(); advance(null); });
$("pause").addEventListener("click", stop);
$("step").addEventListener("click", () => advance(null));
$("pass").addEventListener("click", () => advance(null));
$("show-match").addEventListener("click", () => showPage(false));
$("show-tournament").addEventListener("click", () => showPage(true));
$("tournament-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("run-tournament").disabled = true;
  $("tournament-status").textContent = "Running tournament…";
  $("tournament-results").replaceChildren();
  try {
    const report = await api("/api/tournament", {
      seed: $("seed").valueAsNumber, openings: $("openings").valueAsNumber,
      depth: $("tournament-depth").valueAsNumber,
    });
    tournamentResults(report);
    $("tournament-status").textContent = report.total_matches + " matches completed · seed " + report.config.seed;
  } catch (error) {
    $("tournament-status").textContent = error.message;
  } finally {
    $("run-tournament").disabled = false;
  }
});

async function init() {
  for (let index = 0; index < 64; index += 1) {
    const button = element("button", undefined, "square");
    button.classList.toggle("alt", (Math.floor(index / 8) + index % 8) % 2 === 1);
    button.addEventListener("click", () => advance(index));
    squares.push(button);
    $("board").append(button);
  }
  controls();
  try {
    const {agents} = await api("/api/options");
    $("white-agent").replaceChildren(...agents.map((name) => new Option(name)));
    $("black-agent").replaceChildren(new Option("Human", "Human"), ...agents.map((name) => new Option(name)));
    applyMode();
    await reset();
  } catch (error) {
    setError(error);
    $("status").textContent = "Could not load match settings.";
  }
}

init();
