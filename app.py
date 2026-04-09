from __future__ import annotations

import base64
import io
import json
import os
import re
import shutil
import socket
import subprocess
from datetime import timedelta
from pathlib import Path
from threading import Lock

import qrcode
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for

from game import BracketType, Game, LeaderType, Site


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATE_FILE = DATA_DIR / "game_state.json"
TEMPLATE_STATE_FILE = DATA_DIR / "game_state.template.json"

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-change-me"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)

STATE_LOCK = Lock()


def _default_game_dict():
    return Game("Brack Idea Ring").to_dict()


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def _read_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _ensure_template_state():
    if not TEMPLATE_STATE_FILE.exists():
        _write_json(TEMPLATE_STATE_FILE, _default_game_dict())


def _ensure_working_state():
    _ensure_template_state()
    if not STATE_FILE.exists():
        shutil.copyfile(TEMPLATE_STATE_FILE, STATE_FILE)


def _load_game():
    _ensure_working_state()
    return Game.from_dict(_read_json(STATE_FILE))


GAME = _load_game()


def save_game():
    _write_json(STATE_FILE, GAME.to_dict())


def state_version():
    if not STATE_FILE.exists():
        return "0"
    return str(STATE_FILE.stat().st_mtime_ns)


def _sanitize_save_name(name):
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip()).strip("-").lower()
    return slug[:64]


def _save_file_path(save_name):
    return DATA_DIR / f"game_state.{save_name}.json"


def list_saved_states():
    if not DATA_DIR.exists():
        return []
    names = []
    for path in DATA_DIR.glob("game_state.*.json"):
        if path.name == TEMPLATE_STATE_FILE.name:
            continue
        name = path.name[len("game_state.") : -len(".json")]
        if name:
            names.append(name)
    return sorted(set(names))


def reset_from_template():
    global GAME
    _ensure_template_state()
    GAME = Game.from_dict(_read_json(TEMPLATE_STATE_FILE))
    save_game()


def save_named_state(save_name):
    safe_name = _sanitize_save_name(save_name)
    if not safe_name:
        return None
    _write_json(_save_file_path(safe_name), GAME.to_dict())
    return safe_name


def load_named_state(save_name):
    global GAME
    safe_name = _sanitize_save_name(save_name)
    if not safe_name:
        return None
    state_path = _save_file_path(safe_name)
    if not state_path.exists():
        return None
    GAME = Game.from_dict(_read_json(state_path))
    save_game()
    return safe_name


def login_url():
    return url_for("user_login", _external=True)


def _is_loopback_host(host):
    return host in {"127.0.0.1", "localhost", "::1"}


def _local_ip_address():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def local_base_url():
    port = request.environ.get("SERVER_PORT", "5000")
    return f"http://127.0.0.1:{port}"


def internet_base_url():
    configured = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if configured:
        return configured
    host = request.host.split(":", 1)[0]
    port = request.environ.get("SERVER_PORT", "5000")
    if _is_loopback_host(host):
        host = _local_ip_address()
    return f"http://{host}:{port}"


def current_wifi_ssid():
    airport_cmd = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
    try:
        output = subprocess.check_output([airport_cmd, "-I"], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return None
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if line.startswith("SSID:"):
            return line.split(":", 1)[1].strip() or None
    return None


def wifi_qr_payload(ssid):
    if not ssid:
        return None
    escaped = ssid.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace(":", "\\:")
    return f"WIFI:T:WPA;S:{escaped};;"


def is_local_request():
    remote = (request.remote_addr or "").lower()
    return remote in {"127.0.0.1", "::1", "::ffff:127.0.0.1"}


def require_local_access():
    if not is_local_request():
        abort(403)


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


def _get_value(data, key, default=None):
    if hasattr(data, "get"):
        return data.get(key, default)
    return default


def _get_bool(data, key):
    value = _get_value(data, key)
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "on", "yes"}


def _get_list(data, key):
    if hasattr(data, "getlist"):
        values = data.getlist(key)
        if values:
            return values
    value = _get_value(data, key)
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def perform_action(action, data):
    with STATE_LOCK:
        if action == "create_team":
            name = (_get_value(data, "name", "") or "").strip()
            description = (_get_value(data, "description", "") or "").strip()
            color = (_get_value(data, "color", "#2563eb") or "#2563eb").strip() or "#2563eb"
            if name:
                GAME.create_team(name, description=description, color=color)
                save_game()
        elif action == "update_team":
            team_id = _get_value(data, "team_id")
            GAME.update_team(
                team_id,
                name=(_get_value(data, "name", "") or "").strip() or None,
                description=(_get_value(data, "description", "") or "").strip(),
                color=(_get_value(data, "color", "") or "").strip() or None,
            )
            save_game()
        elif action == "reorder_teams":
            GAME.reorder_teams(_get_list(data, "team_ids"))
            save_game()
        elif action == "assign_leader":
            leader_id = _get_value(data, "leader_id")
            team_id = _get_value(data, "team_id")
            GAME.assign_leader_to_team(leader_id, team_id)
            save_game()
        elif action == "update_leader":
            leader_id = _get_value(data, "leader_id")
            if leader_id:
                GAME.update_leader(
                    leader_id,
                    name=(_get_value(data, "name", "") or "").strip() or None,
                    leader_type=_get_value(data, "leader_type") or None,
                    site=_get_value(data, "site") or None,
                    can_submit_ideas=_get_bool(data, "can_submit_ideas") if _get_value(data, "can_submit_ideas") is not None else None,
                )
                save_game()
        elif action == "move_leader":
            leader_id = _get_value(data, "leader_id")
            team_id = _get_value(data, "team_id")
            if leader_id and team_id:
                GAME.assign_leader_to_team(leader_id, team_id)
                save_game()
        elif action == "select_team_submitter":
            team_id = _get_value(data, "team_id")
            leader_id = _get_value(data, "leader_id")
            if team_id and leader_id and GAME.select_team_submitter(team_id, leader_id):
                save_game()
        elif action == "clear_team_submitter":
            team_id = _get_value(data, "team_id")
            if team_id in GAME.team_submitters:
                del GAME.team_submitters[team_id]
                save_game()
        elif action == "set_leader_permission":
            leader_id = _get_value(data, "leader_id")
            leader = GAME.get_leader(leader_id)
            if leader:
                leader.can_submit_ideas = _get_bool(data, "can_submit_ideas")
                leader.type = _get_value(data, "leader_type") or leader.type
                leader.site = _get_value(data, "site") or leader.site
                save_game()
        elif action == "create_bracket":
            name = (_get_value(data, "name", "") or "").strip()
            if name:
                GAME.create_bracket(
                    name,
                    bracket_type=_get_value(data, "bracket_type") or None,
                    description=(_get_value(data, "description", "") or "").strip(),
                    output_count=int(_get_value(data, "output_count")) if _get_value(data, "output_count") else 0,
                )
                save_game()
        elif action == "update_bracket":
            bracket_id = _get_value(data, "bracket_id")
            GAME.update_bracket(
                bracket_id,
                name=(_get_value(data, "name", "") or "").strip() or None,
                bracket_type=_get_value(data, "bracket_type") or None,
                description=(_get_value(data, "description", "") or "").strip(),
                output_count=int(_get_value(data, "output_count")) if _get_value(data, "output_count") is not None and _get_value(data, "output_count") != "" else None,
            )
            save_game()
        elif action == "reorder_brackets":
            GAME.reorder_brackets(_get_list(data, "bracket_ids"))
            save_game()
        elif action == "clone_output_to_bracket":
            source_bracket_id = _get_value(data, "source_bracket_id")
            slot = _get_value(data, "slot")
            target_bracket_id = _get_value(data, "target_bracket_id")
            if GAME.clone_output_to_bracket(source_bracket_id, slot, target_bracket_id):
                save_game()
        elif action == "set_bracket_seed_order":
            bracket_id = _get_value(data, "bracket_id")
            ordered_idea_ids = _get_list(data, "ordered_idea_ids")
            if GAME.set_bracket_seed_order(bracket_id, ordered_idea_ids) is not None:
                save_game()
        elif action == "create_custom_matchup":
            name = (_get_value(data, "name", "") or "").strip()
            description = (_get_value(data, "description", "") or "").strip()
            left_idea_id = _get_value(data, "left_idea_id")
            right_idea_id = _get_value(data, "right_idea_id")
            if GAME.create_custom_matchup(name, description, left_idea_id, right_idea_id):
                save_game()
        elif action == "assign_matchup_to_round":
            matchup_id = _get_value(data, "matchup_id")
            round_id = _get_value(data, "round_id")
            if GAME.assign_matchup_to_round(matchup_id, round_id):
                save_game()
        elif action == "reorder_matchups":
            ordered_matchup_ids = _get_list(data, "matchup_ids")
            GAME.reorder_matchups(ordered_matchup_ids)
            save_game()
        elif action == "reorder_round_matchups":
            round_id = _get_value(data, "round_id")
            ordered_matchup_ids = _get_list(data, "matchup_ids")
            if GAME.reorder_round_matchups(round_id, ordered_matchup_ids):
                save_game()
        elif action == "add_round":
            GAME.add_round()
            save_game()
        elif action == "remove_round":
            GAME.remove_round()
            save_game()
        elif action == "create_idea":
            title = (_get_value(data, "title", "") or "").strip()
            description = (_get_value(data, "description", "") or "").strip()
            assigned_team_id = _get_value(data, "assigned_team_id") or None
            assigned_leader_id = _get_value(data, "assigned_leader_id") or None
            category = (_get_value(data, "category", "General") or "General").strip() or "General"
            if title:
                GAME.create_idea(
                    title,
                    description,
                    assigned_team_id=assigned_team_id,
                    assigned_leader_id=assigned_leader_id,
                    category=category,
                )
                save_game()
        elif action == "update_idea":
            idea_id = _get_value(data, "idea_id")
            GAME.update_idea(
                idea_id,
                title=(_get_value(data, "title", "") or "").strip() or None,
                description=(_get_value(data, "description", "") or "").strip(),
                bracket_id=_get_value(data, "bracket_id") or None,
                category=_get_value(data, "category") or None,
                assigned_team_id=_get_value(data, "assigned_team_id"),
                assigned_leader_id=_get_value(data, "assigned_leader_id"),
                point_miranda=_get_value(data, "point_miranda"),
                point_kirrawee=_get_value(data, "point_kirrawee"),
                backup_miranda=_get_value(data, "backup_miranda"),
                backup_kirrawee=_get_value(data, "backup_kirrawee"),
            )
            save_game()
        elif action == "create_category":
            name = (_get_value(data, "name", "") or "").strip()
            color = (_get_value(data, "color", "#38bdf8") or "#38bdf8").strip() or "#38bdf8"
            if name:
                GAME.ensure_category(name, color)
                save_game()
        elif action == "update_category":
            old_name = (_get_value(data, "old_name", "") or "").strip()
            new_name = (_get_value(data, "new_name", "") or "").strip()
            color = (_get_value(data, "color", "") or "").strip() or None
            if old_name and new_name:
                GAME.rename_category(old_name, new_name, color=color)
                save_game()
        elif action == "move_idea":
            GAME.move_idea_to_bracket(_get_value(data, "idea_id"), _get_value(data, "bracket_id"))
            save_game()
        elif action == "delete_idea":
            GAME.remove_idea(_get_value(data, "idea_id"))
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
            GAME.set_stage(int(_get_value(data, "stage_index", 0)))
            save_game()
        elif action == "add_round":
            GAME.add_round()
            save_game()
        elif action == "remove_round":
            GAME.remove_round()
            save_game()
        elif action == "auto_fill_round":
            GAME.auto_fill_round()
            save_game()
        elif action == "reset_stage":
            if GAME.reset_current_stage():
                save_game()
        elif action == "next_matchup":
            GAME.next_matchup()
            save_game()
        elif action == "previous_matchup":
            GAME.previous_matchup()
            save_game()
        elif action == "toggle_show_previous_matchups":
            GAME.toggle_show_previous_matchups()
            save_game()
        elif action == "toggle_result_view":
            GAME.toggle_result_view()
            save_game()
        elif action == "set_countdown_seconds":
            GAME.set_countdown_seconds(_get_value(data, "countdown_seconds", 60))
            save_game()
        elif action == "pause_countdown":
            if GAME.pause_matchup_countdown() is not None:
                save_game()
        elif action == "resume_countdown":
            if GAME.resume_matchup_countdown() is not None:
                save_game()
        elif action == "speak_to_idea":
            if GAME.pause_matchup_countdown() is not None:
                GAME.message = "Countdown paused for speaking."
                save_game()
        elif action == "reset_to_template":
            reset_from_template()
            flash("Game state reset to template.")
        elif action == "save_state":
            saved_name = save_named_state(_get_value(data, "save_name", ""))
            if saved_name:
                flash(f"Saved state: {saved_name}")
            else:
                flash("Please enter a valid save name.")
        elif action == "load_state":
            loaded_name = load_named_state(_get_value(data, "load_state_name", ""))
            if loaded_name:
                flash(f"Loaded state: {loaded_name}")
            else:
                flash("Could not load the selected state.")


def submit_action(action):
    perform_action(action, request.form)


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
        "show_nav": True,
        "header_title": "BRACK-IDEA-RING",
        "auto_refresh": False,
        "state_poll_url": url_for("state_meta"),
    }


@app.get("/api/state-meta")
def state_meta():
    return jsonify({"version": state_version(), "stage": GAME.stage, "leader_count": len(GAME.leaders)})


@app.get("/")
def root():
    return redirect(url_for("game_screen"))


@app.get("/master")
def master_screen():
    require_local_access()
    teams = GAME.ordered_teams()
    teams_needing_submitter = [team for team in teams if team.id != "unassigned" and not GAME.team_submitters.get(team.id)]
    brackets = GAME.ordered_brackets()
    leaders = GAME.sorted_leaders()
    ideas = [GAME.idea_display(idea) for idea in GAME.ideas_sorted()]
    return render_template(
        "master.html",
        game=GAME,
        teams=teams,
        brackets=brackets,
        leaders=leaders,
        ideas=ideas,
        categories=[{"name": name, "color": color} for name, color in sorted(GAME.categories.items(), key=lambda item: item[0].lower())],
        leaders_by_team={team.id: [leader for leader in leaders if leader.team_id == team.id] for team in teams},
        teams_needing_submitter=teams_needing_submitter,
        team_submitters=dict(GAME.team_submitters),
        volunteer_ids=set(GAME.submitter_volunteers.keys()),
        pairing_matchups=GAME.pairing_matchups_display(),
        pairing_live_matchups=GAME.active_round_matchups_display(),
        ideas_by_bracket={
            bracket.id: [
                idea
                for idea in ideas
                if (idea.get("bracket_id") == bracket.id) or (idea.get("bracket_id") is None and bracket.id == "main")
            ]
            for bracket in brackets
        },
        outputs_by_bracket={bracket.id: GAME.bracket_output_view(bracket) for bracket in brackets},
        bracket_previews={bracket.id: GAME.bracket_preview(bracket) for bracket in brackets},
        standings_brackets=GAME.standings_bracket_views(),
        rounds_display=GAME.rounds_display(),
        stage_options=list(enumerate(GAME.stage_sequence())),
        saved_states=list_saved_states(),
        auto_refresh=True,
        page_name="master",
    )


@app.post("/master/action")
def master_action():
    require_local_access()
    submit_action(request.form.get("action", ""))
    return redirect(url_for("master_screen"))


@app.post("/api/master/action")
def master_action_api():
    require_local_access()
    payload = request.get_json(silent=True) or {}
    perform_action(payload.get("action", ""), payload)
    return jsonify({"ok": True, "version": state_version()})


@app.get("/game")
def game_screen():
    internet_login = f"{internet_base_url()}/user/login"
    ssid = current_wifi_ssid()
    wifi_payload = wifi_qr_payload(ssid)
    intro_bg = url_for("static", filename="images/game-intro.png")
    round_bg = url_for("static", filename="images/game-round.png")
    active_matchups = GAME.active_round_matchups_display()
    current_matchup_index = GAME.pairing_round.get("current_matchup_index", 0)
    current_matchup = active_matchups[current_matchup_index] if active_matchups and 0 <= current_matchup_index < len(active_matchups) else None
    final_bracket = GAME.final_bracket()
    final_rankings = GAME.final_bracket_rankings()
    return render_template(
        "game.html",
        game_summary=GAME.summary(),
        game=GAME,
        current_matchup=current_matchup,
        current_matchup_remaining=GAME.current_matchup_countdown_remaining(),
        current_matchup_end=GAME.current_matchup_countdown_end(),
        current_matchup_paused=GAME.pairing_round.get("countdown_paused", False),
        final_bracket=final_bracket,
        final_rankings=final_rankings,
        intro_bg_url=intro_bg,
        round_bg_url=round_bg,
        winner_image_url=url_for("static", filename="images/winner.png"),
        tie_image_url=url_for("static", filename="images/tie.png"),
        qr_data_url=make_qr_data_url(internet_login),
        login_url=internet_login,
        internet_login_url=internet_login,
        wifi_ssid=ssid,
        wifi_qr_data_url=make_qr_data_url(wifi_payload) if wifi_payload else None,
        show_nav=False,
        show_header=False,
        header_title="",
        full_bleed=True,
        auto_refresh=True,
        page_name="game",
    )


@app.route("/user", methods=["GET"])
def user_screen():
    leader = current_leader()
    if not leader:
        return render_template(
            "user_login.html",
            game=GAME,
            show_nav=False,
            show_header=False,
            auto_refresh=True,
            page_name="user-login",
        )
    team = GAME.get_team(leader.team_id) if leader.team_id else None
    team_submitter_id = GAME.team_submitters.get(team.id) if team else None
    team_submitter = GAME.get_leader(team_submitter_id) if team_submitter_id else None
    team_ideas = [GAME.idea_display(idea) for idea in GAME.team_ideas(team.id if team else None)]
    can_submit_ideas = GAME.can_leader_submit_ideas(leader)
    is_team_submitter = GAME.is_team_submitter(leader.id)
    
    # For pairing stage, only show the current matchup
    current_matchup = GAME.current_matchup()
    pairing_matchups = []
    if current_matchup:
        # Build display data for current matchup only
        matchup_id = current_matchup.get("id")
        idea_ids = current_matchup.get("idea_ids", [])
        votes = GAME.pairing_round.get("votes", {}).get(matchup_id, {})
        ideas = []
        for idea_id in idea_ids:
            idea = GAME.ideas.get(idea_id)
            if not idea:
                continue
            vote_count = sum(1 for selected in votes.values() if selected == idea_id)
            ideas.append({
                "id": idea.id,
                "title": idea.title,
                "description": idea.description,
                "votes": vote_count,
                "point_ids": idea.point,
                "backup_ids": idea.backup_point,
                "point": {site: GAME.get_leader(leader_id).name if (leader_id := idea.point.get(site)) else None for site in [Site.MIRANDA.value, Site.KIRRAWEE.value]},
                "backup": {site: GAME.get_leader(leader_id).name if (leader_id := idea.backup_point.get(site)) else None for site in [Site.MIRANDA.value, Site.KIRRAWEE.value]},
            })
        
        # Calculate cooldowns for current matchup
        my_site = leader.site or ""
        site_key = f"{matchup_id}:{my_site}"
        cooldown_left = GAME.cooldown_remaining(matchup_id, my_site)
        cooldown_until = GAME.pairing_round.get("cooldowns", {}).get(site_key, 0)
        
        pairing_matchups = [{
            "id": matchup_id,
            "ideas": ideas,
            "cooldowns": {my_site: cooldown_left} if my_site else {},
            "cooldown_untils": {my_site: cooldown_until} if my_site else {},
            "paused": GAME.pairing_round.get("countdown_paused", False),
        }]
    
    return render_template(
        "user_dashboard.html",
        game=GAME,
        leader=leader,
        team=team,
        team_submitter=team_submitter,
        team_has_submitter=bool(team_submitter),
        team_ideas=team_ideas,
        can_submit_ideas=can_submit_ideas,
        is_team_submitter=is_team_submitter,
        pairing_matchups=pairing_matchups,
        show_nav=False,
        show_header=False,
        auto_refresh=True,
        page_name="user-dashboard",
    )


@app.route("/user/login", methods=["GET", "POST"])
def user_login():
    if request.method == "GET":
        return render_template(
            "user_login.html",
            game=GAME,
            show_nav=False,
            show_header=False,
            auto_refresh=True,
            page_name="user-login",
        )
    name = request.form.get("name", "").strip()
    site = request.form.get("site") or None
    leader_type = request.form.get("leader_type") or None
    if not name:
        flash("Please enter a name to continue.")
        return redirect(url_for("user_screen"))
    with STATE_LOCK:
        existing = next((leader for leader in GAME.leaders.values() if leader.name.lower() == name.lower()), None)
        if existing is None:
            existing = GAME.create_leader(name=name, site=site, leader_type=leader_type, can_submit_ideas=False)
        else:
            if site:
                existing.site = site
            if leader_type:
                existing.type = leader_type
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
            idea = GAME.submit_idea_for_leader(leader, title, description)
            if idea:
                save_game()
            else:
                flash("You cannot submit ideas in this stage.")
    return redirect(url_for("user_screen"))


@app.post("/user/volunteer-submitter")
def user_volunteer_submitter():
    leader = current_leader()
    if not leader:
        return redirect(url_for("user_screen"))
    with STATE_LOCK:
        if GAME.stage == "team-leads-ideas":
            GAME.volunteer_submitter(leader.id, volunteer=True)
            save_game()
    return redirect(url_for("user_screen"))


@app.post("/user/vote")
def user_vote_idea():
    leader = current_leader()
    if not leader:
        return redirect(url_for("user_screen"))
    matchup_id = request.form.get("matchup_id", "")
    idea_id = request.form.get("idea_id", "")
    with STATE_LOCK:
        if GAME.cast_vote(matchup_id, idea_id, leader.id):
            save_game()
        else:
            flash("Could not record vote.")
    return redirect(url_for("user_screen"))


@app.post("/user/nominate")
def user_nominate_role():
    leader = current_leader()
    if not leader:
        return redirect(url_for("user_screen"))
    matchup_id = request.form.get("matchup_id", "")
    idea_id = request.form.get("idea_id", "")
    role = request.form.get("role", "point")
    with STATE_LOCK:
        ok, message = GAME.nominate_point_role(matchup_id, idea_id, leader, role=role)
        if ok:
            save_game()
        elif message:
            flash(message)
    return redirect(url_for("user_screen"))


@app.post("/user/speak-to-idea")
def user_speak_to_idea():
    leader = current_leader()
    if not leader:
        return redirect(url_for("user_screen"))
    matchup_id = request.form.get("matchup_id", "")
    idea_id = request.form.get("idea_id", "")
    with STATE_LOCK:
        if GAME._matchup_by_id(matchup_id) and idea_id:
            if GAME.pause_matchup_countdown() is not None:
                GAME.message = f"Speaking about {GAME.get_idea(idea_id).title if GAME.get_idea(idea_id) else 'an idea'}"
                save_game()
    return redirect(url_for("user_screen"))


@app.post("/user/nominate/opt-out")
def user_nominate_opt_out():
    leader = current_leader()
    if not leader:
        return redirect(url_for("user_screen"))
    matchup_id = request.form.get("matchup_id", "")
    idea_id = request.form.get("idea_id", "")
    with STATE_LOCK:
        ok, message = GAME.opt_out_nomination(matchup_id, idea_id, leader)
        if ok:
            save_game()
        if message:
            flash(message)
    return redirect(url_for("user_screen"))


if __name__ == "__main__":
    debug = os.getenv("DEBUG", "true").lower() == "true"
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5002"))
    app.run(debug=debug, host=host, port=port)