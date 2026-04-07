from __future__ import annotations

import base64
import io
import json
from datetime import timedelta
from pathlib import Path
from threading import Lock

import qrcode
from flask import Flask, flash, redirect, render_template, request, session, url_for

from game import BracketType, Game, LeaderType, Site


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATE_FILE = DATA_DIR / "game_state.json"

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-change-me"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)

STATE_LOCK = Lock()


def _load_game():
    if STATE_FILE.exists():
        with STATE_FILE.open("r", encoding="utf-8") as handle:
            return Game.from_dict(json.load(handle))
    return Game("Brack Idea Ring")


GAME = _load_game()


def save_game():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with STATE_FILE.open("w", encoding="utf-8") as handle:
        json.dump(GAME.to_dict(), handle, indent=2)


def login_url():
    return url_for("user_login", _external=True)


def make_qr_data_url(text):
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(text)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def current_leader():
    leader_id = session.get("leader_id")
    return GAME.get_leader(leader_id) if leader_id else None


def submit_action(action):
    with STATE_LOCK:
        if action == "create_team":
            name = request.form.get("name", "").strip()
            description = request.form.get("description", "").strip()
            color = request.form.get("color", "#2563eb").strip() or "#2563eb"
            if name:
                GAME.create_team(name, description=description, color=color)
                save_game()
        elif action == "update_team":
            team_id = request.form.get("team_id")
            GAME.update_team(
                team_id,
                name=request.form.get("name", "").strip() or None,
                description=request.form.get("description", "").strip(),
                color=request.form.get("color", "").strip() or None,
            )
            save_game()
        elif action == "assign_leader":
            leader_id = request.form.get("leader_id")
            team_id = request.form.get("team_id")
            GAME.assign_leader_to_team(leader_id, team_id)
            save_game()
        elif action == "set_leader_permission":
            leader_id = request.form.get("leader_id")
            leader = GAME.get_leader(leader_id)
            if leader:
                leader.can_submit_ideas = request.form.get("can_submit_ideas") == "on"
                leader.type = request.form.get("leader_type") or leader.type
                leader.site = request.form.get("site") or leader.site
                save_game()
        elif action == "create_bracket":
            name = request.form.get("name", "").strip()
            if name:
                GAME.create_bracket(
                    name,
                    bracket_type=request.form.get("bracket_type") or None,
                    target_count=int(request.form["target_count"]) if request.form.get("target_count") else None,
                    description=request.form.get("description", "").strip(),
                )
                save_game()
        elif action == "update_bracket":
            bracket_id = request.form.get("bracket_id")
            GAME.update_bracket(
                bracket_id,
                name=request.form.get("name", "").strip() or None,
                bracket_type=request.form.get("bracket_type") or None,
                target_count=int(request.form["target_count"]) if request.form.get("target_count") else None,
                description=request.form.get("description", "").strip(),
                feeds_into=request.form.getlist("feeds_into"),
            )
            save_game()
        elif action == "link_brackets":
            source = request.form.get("source_bracket_id")
            target = request.form.get("target_bracket_id")
            bracket = GAME.get_bracket(source)
            if bracket and target and target not in bracket.feeds_into:
                bracket.feeds_into.append(target)
                save_game()
        elif action == "create_idea":
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            created_by_id = request.form.get("created_by_id")
            if title:
                GAME.create_idea(title, description, created_by_id=created_by_id)
                save_game()
        elif action == "update_idea":
            idea_id = request.form.get("idea_id")
            GAME.update_idea(
                idea_id,
                title=request.form.get("title", "").strip() or None,
                description=request.form.get("description", "").strip(),
                status=request.form.get("status") or None,
                bracket_id=request.form.get("bracket_id") or None,
            )
            save_game()
        elif action == "move_idea":
            GAME.move_idea_to_bracket(request.form.get("idea_id"), request.form.get("bracket_id"))
            save_game()
        elif action == "delete_idea":
            GAME.remove_idea(request.form.get("idea_id"))
            save_game()
        elif action == "pause":
            GAME.pause()
            save_game()
        elif action == "resume":
            GAME.resume()
            save_game()
        elif action == "advance_stage":
            GAME.advance_stage()
            save_game()
        elif action == "rewind_stage":
            GAME.rewind_stage()
            save_game()
        elif action == "set_stage":
            GAME.set_stage(int(request.form.get("stage_index", 0)))
            save_game()


@app.before_request
def ensure_session_defaults():
    session.permanent = True


@app.context_processor
def inject_globals():
    return {
        "game": GAME,
        "login_url": login_url(),
        "leader_type_options": [option.value for option in LeaderType],
        "site_options": [option.value for option in Site],
        "bracket_type_options": [option.value for option in BracketType],
    }


@app.get("/")
def root():
    return redirect(url_for("game_screen"))


@app.get("/master")
def master_screen():
    return render_template(
        "master.html",
        game=GAME,
        teams=list(GAME.teams.values()),
        brackets=list(GAME.brackets.values()),
        leaders=list(GAME.leaders.values()),
        ideas=list(GAME.ideas.values()),
        stage_options=list(enumerate(Game.STAGES)),
    )


@app.post("/master/action")
def master_action():
    submit_action(request.form.get("action", ""))
    return redirect(url_for("master_screen"))


@app.get("/game")
def game_screen():
    return render_template(
        "game.html",
        game_summary=GAME.summary(),
        qr_data_url=make_qr_data_url(login_url()),
        login_url=login_url(),
    )


@app.route("/user", methods=["GET"])
def user_screen():
    leader = current_leader()
    if not leader:
        return render_template("user_login.html", game=GAME)
    team = GAME.get_team(leader.team_id) if leader.team_id else None
    leader_ideas = [idea for idea in GAME.ideas.values() if idea.created_by_id == leader.id]
    team_ideas = [idea for idea in GAME.ideas.values() if team and idea.created_by_id in {member.id for member in team.get_members()}]
    can_submit = leader.can_submit_ideas or GAME.stage in {"all-ideas"}
    return render_template(
        "user_dashboard.html",
        game=GAME,
        leader=leader,
        team=team,
        leader_ideas=leader_ideas,
        team_ideas=team_ideas,
        can_submit=can_submit,
    )


@app.route("/user/login", methods=["GET", "POST"])
def user_login():
    if request.method == "GET":
        return render_template("user_login.html", game=GAME)
    name = request.form.get("name", "").strip()
    site = request.form.get("site") or None
    if not name:
        flash("Please enter a name to continue.")
        return redirect(url_for("user_screen"))
    with STATE_LOCK:
        existing = next((leader for leader in GAME.leaders.values() if leader.name.lower() == name.lower()), None)
        if existing is None:
            existing = GAME.create_leader(name=name, site=site, can_submit_ideas=False)
            save_game()
        session["leader_id"] = existing.id
        session["leader_name"] = existing.name
    return redirect(url_for("user_screen"))


@app.post("/user/logout")
def user_logout():
    session.pop("leader_id", None)
    session.pop("leader_name", None)
    return redirect(url_for("user_screen"))


@app.post("/user/idea")
def user_submit_idea():
    leader = current_leader()
    if not leader:
        return redirect(url_for("user_screen"))
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    if title:
        with STATE_LOCK:
            GAME.create_idea(title, description, created_by_id=leader.id)
            save_game()
    return redirect(url_for("user_screen"))


if __name__ == "__main__":
    app.run(debug=True)