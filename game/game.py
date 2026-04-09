from __future__ import annotations

import time

from .bracket import BRACKET_CLASS_BY_TYPE, Bracket, BracketType
from .gameplay import STAGE_DEFINITIONS
from .idea import Idea
from .leader import Leader, LeaderType, Site
from .matchup import Matchup
from .round import Round
from .team import Team


class Game:
    BASE_STAGE_KEYS = [definition.key for definition in STAGE_DEFINITIONS if not definition.key.startswith("pairing")]
    NOMINATION_COOLDOWN_SECONDS = 3

    def __init__(self, name):
        self.name = name
        self.teams = {}
        self.team_order = []
        self.brackets = {}
        self.bracket_order = []
        self.leaders = {}
        self.ideas = {}
        self.categories = {"General": "#38bdf8"}
        self.current_stage = 0
        self.round_count = 1
        self.rounds = [Round(number=1)]
        self.is_paused = False
        self.message = "Game ready."
        self.team_submitters = {}
        self.submitter_volunteers = {}
        self.pairing_round = {
            "matchups": [],
            "votes": {},
            "point_nominations": {},
            "backup_nominations": {},
            "cooldowns": {},
            "vote_timestamps": {},
            "point_nomination_times": {},
            "results": {},
            "current_matchup_index": 0,
            "show_previous_matchups": False,
            "show_result": False,
            "countdown_seconds": 60,
            "matchup_started_at": None,
            "countdown_paused": False,
            "countdown_pause_started_at": None,
            "countdown_paused_remaining": None,
        }
        self.teams["unassigned"] = Team("Unassigned", team_id="unassigned", description="Leaders that have not been assigned to a team yet.", color="#64748b")
        self.brackets["main"] = Bracket("Main Bracket", bracket_id="main", bracket_type=BracketType.SWISS.value, description="The root bracket that receives new ideas.", output_count=0)
        self.team_order = ["unassigned"]
        self.bracket_order = ["main"]

    @property
    def stage(self):
        sequence = self.stage_sequence()
        if not sequence:
            return "setup"
        return sequence[max(0, min(self.current_stage, len(sequence) - 1))]

    def stage_sequence(self):
        self._sync_rounds()
        sequence = ["setup", "team-leads-ideas", "all-ideas", "bracket-sorting"]
        for index in range(1, max(1, int(self.round_count or 1)) + 1):
            sequence.append(f"round-{index}")
            if index < max(1, int(self.round_count or 1)):
                sequence.append(f"prepare-round-{index + 1}")
        sequence.extend(["scoring", "complete"])
        return sequence

    def _sync_rounds(self):
        desired = max(1, int(self.round_count or 1))
        while len(self.rounds) < desired:
            self.rounds.append(Round(number=len(self.rounds) + 1))
        while len(self.rounds) > desired:
            self.rounds.pop()
        for idx, round_obj in enumerate(self.rounds, start=1):
            round_obj.number = idx
            round_obj.name = f"Round {idx}"

    def round_for_number(self, round_number):
        self._sync_rounds()
        if round_number <= 0 or round_number > len(self.rounds):
            return None
        return self.rounds[round_number - 1]

    def current_round_number(self):
        if self.is_round_stage():
            try:
                return int(self.stage.split("-", 1)[1])
            except Exception:
                return 1
        if self.is_prepare_stage():
            try:
                return int(self.stage.split("-")[-1])
            except Exception:
                return 1
        return 1

    def rounds_display(self):
        matchup_map = {matchup.get("id"): matchup for matchup in self.pairing_matchups_display()}
        rows = []
        self._sync_rounds()
        for round_obj in self.rounds:
            round_matchups = [matchup_map[mid] for mid in round_obj.matchup_ids if mid in matchup_map]
            rows.append({"id": round_obj.id, "number": round_obj.number, "name": round_obj.name, "matchups": round_matchups})
        return rows

    def assign_matchup_to_round(self, matchup_id, round_id):
        self._sync_rounds()
        if not matchup_id or not round_id:
            return False
        target = next((round_obj for round_obj in self.rounds if round_obj.id == round_id), None)
        if not target:
            return False
        for round_obj in self.rounds:
            round_obj.remove_matchup(matchup_id)
        target.add_matchup(matchup_id)
        for matchup in self.pairing_round.get("matchups", []):
            if matchup.get("id") == matchup_id:
                matchup["round_id"] = target.id
                matchup["bracket_round"] = target.number
                break
        return True

    def reorder_matchups(self, ordered_matchup_ids):
        order = [matchup_id for matchup_id in ordered_matchup_ids if matchup_id]
        by_id = {matchup.get("id"): matchup for matchup in self.pairing_round.get("matchups", [])}
        reordered = [by_id[mid] for mid in order if mid in by_id]
        remainder = [matchup for matchup in self.pairing_round.get("matchups", []) if matchup.get("id") not in order]
        self.pairing_round["matchups"] = [*reordered, *remainder]
        order_index = {matchup.get("id"): idx for idx, matchup in enumerate(self.pairing_round["matchups"]) if matchup.get("id")}
        for idx, matchup in enumerate(self.pairing_round["matchups"], start=1):
            matchup["order"] = idx
        for round_obj in self.rounds:
            round_obj.matchup_ids = [mid for mid in round_obj.matchup_ids if mid in by_id]
            round_obj.matchup_ids.sort(key=lambda mid: order_index.get(mid, 10**9))
        return self.pairing_round["matchups"]

    def reorder_round_matchups(self, round_id, ordered_matchup_ids):
        self._sync_rounds()
        target_round = next((round_obj for round_obj in self.rounds if round_obj.id == round_id), None)
        if not target_round:
            return False
        in_round = set(target_round.matchup_ids)
        ordered = [matchup_id for matchup_id in ordered_matchup_ids if matchup_id in in_round]
        remainder = [matchup_id for matchup_id in target_round.matchup_ids if matchup_id not in ordered]
        target_round.matchup_ids = [*ordered, *remainder]
        for matchup in self.pairing_round.get("matchups", []):
            if matchup.get("id") in in_round:
                matchup["order"] = target_round.matchup_ids.index(matchup["id"]) + 1
        return True

    def set_countdown_seconds(self, seconds):
        try:
            value = max(0, int(seconds))
        except Exception:
            return self.pairing_round.get("countdown_seconds", 60)
        self.pairing_round["countdown_seconds"] = value
        return value

    def toggle_result_view(self):
        self.pairing_round["show_result"] = not self.pairing_round.get("show_result", False)
        return self.pairing_round["show_result"]

    def set_matchup_started_now(self):
        self.pairing_round["matchup_started_at"] = time.time()
        self.pairing_round["countdown_paused"] = False
        self.pairing_round["countdown_pause_started_at"] = None
        self.pairing_round["countdown_paused_remaining"] = None

    def _current_countdown_duration(self):
        try:
            return max(0, int(self.pairing_round.get("countdown_seconds", 60) or 0))
        except Exception:
            return 60

    def pause_matchup_countdown(self):
        if self.pairing_round.get("countdown_paused"):
            return self.current_matchup_countdown_remaining()
        remaining = self.current_matchup_countdown_remaining()
        if remaining is None:
            return None
        self.pairing_round["countdown_paused"] = True
        self.pairing_round["countdown_pause_started_at"] = time.time()
        self.pairing_round["countdown_paused_remaining"] = remaining
        return remaining

    def resume_matchup_countdown(self):
        if not self.pairing_round.get("countdown_paused"):
            return self.current_matchup_countdown_remaining()
        remaining = self.pairing_round.get("countdown_paused_remaining")
        if remaining is None:
            remaining = self.current_matchup_countdown_remaining()
        duration = self._current_countdown_duration()
        if remaining is None:
            remaining = duration
        self.pairing_round["matchup_started_at"] = time.time() - max(0, duration - int(remaining))
        self.pairing_round["countdown_paused"] = False
        self.pairing_round["countdown_pause_started_at"] = None
        self.pairing_round["countdown_paused_remaining"] = None
        return self.current_matchup_countdown_remaining()

    def current_matchup_countdown_remaining(self):
        if self.pairing_round.get("countdown_paused"):
            remaining = self.pairing_round.get("countdown_paused_remaining")
            return int(remaining) if remaining is not None else None
        started_at = self.pairing_round.get("matchup_started_at")
        if not started_at:
            return None
        duration = self._current_countdown_duration()
        return max(0, int(duration - (time.time() - float(started_at))))

    def current_matchup_countdown_end(self):
        if self.pairing_round.get("countdown_paused"):
            remaining = self.pairing_round.get("countdown_paused_remaining")
            if remaining is None:
                return None
            return time.time() + int(remaining)
        started_at = self.pairing_round.get("matchup_started_at")
        if not started_at:
            return None
        duration = self._current_countdown_duration()
        return float(started_at) + duration

    def round_stage_keys(self):
        return [stage for stage in self.stage_sequence() if stage.startswith("round-")]

    def is_round_stage(self, stage_key=None):
        key = stage_key or self.stage
        return key.startswith("round-")

    def is_prepare_stage(self, stage_key=None):
        key = stage_key or self.stage
        return key.startswith("prepare-round-")

    def stage_title(self, stage_key=None):
        key = stage_key or self.stage
        if key.startswith("round-"):
            round_number = key.split("-", 1)[1]
            return f"Round {round_number}"
        if key.startswith("prepare-round-"):
            round_number = key.split("-", 2)[2]
            return f"Prepare Round {round_number}"
        definition = next((definition for definition in STAGE_DEFINITIONS if definition.key == key), None)
        if definition:
            return definition.title
        return key.replace("-", " ").title()

    def stage_label(self):
        return self.stage_title(self.stage)

    def stage_definition(self):
        key = self.stage
        return next((definition for definition in STAGE_DEFINITIONS if definition.key == key), None)

    def add_team(self, team: Team):
        self.teams[team.id] = team
        if team.id not in self.team_order:
            self.team_order.append(team.id)
        return team

    def create_team(self, name, description="", color="#2563eb"):
        return self.add_team(Team(name, description=description, color=color))

    def update_team(self, team_id, *, name=None, description=None, color=None):
        team = self.teams.get(team_id)
        if not team:
            return None
        if name:
            team.name = name
        if description is not None:
            team.description = description
        if color:
            team.color = color
        return team

    def remove_team(self, team):
        team_id = team.id if isinstance(team, Team) else team
        if team_id in self.teams and team_id != "unassigned":
            team_obj = self.teams[team_id]
            for member in list(team_obj.get_members()):
                self.teams["unassigned"].add_member(member)
            del self.teams[team_id]
            if team_id in self.team_order:
                self.team_order.remove(team_id)

    def reorder_teams(self, ordered_team_ids):
        ordered = [team_id for team_id in ordered_team_ids if team_id in self.teams and team_id != "unassigned"]
        if "unassigned" in self.teams and self.teams["unassigned"].get_members():
            self.team_order = ["unassigned", *ordered]
        else:
            self.team_order = ordered

    def ordered_team_ids(self):
        ordered = [team_id for team_id in self.team_order if team_id in self.teams]
        extras = [team_id for team_id in self.teams if team_id not in ordered]
        ordered.extend(extras)
        if "unassigned" in self.teams and not self.teams["unassigned"].get_members():
            ordered = [team_id for team_id in ordered if team_id != "unassigned"]
        elif "unassigned" in self.teams and ordered and ordered[0] != "unassigned":
            ordered = ["unassigned", *[team_id for team_id in ordered if team_id != "unassigned"]]
        return ordered

    def ordered_teams(self):
        return [self.teams[team_id] for team_id in self.ordered_team_ids()]

    def new_player(self, player: Leader):
        self.leaders[player.id] = player
        self.teams["unassigned"].add_member(player)
        return player

    def create_leader(self, name, leader_type=None, site=None, can_submit_ideas=False):
        leader = Leader(name, leader_type=leader_type, site=site, can_submit_ideas=can_submit_ideas)
        return self.new_player(leader)

    def team_for_leader_id(self, leader_id):
        leader = self.leaders.get(leader_id)
        if not leader:
            return None
        return self.team_for_leader(leader)

    def update_leader(self, leader_id, *, name=None, leader_type=None, site=None, can_submit_ideas=None):
        leader = self.leaders.get(leader_id)
        if not leader:
            return None
        if name:
            leader.name = name
        if leader_type is not None:
            leader.type = leader_type
        if site is not None:
            leader.site = site
        if can_submit_ideas is not None:
            leader.can_submit_ideas = can_submit_ideas
        return leader

    def assign_player(self, player: Leader, team_name: str):
        target_team = self.teams.get(team_name) or self.teams.get("unassigned")
        if not target_team:
            return None
        for team in self.teams.values():
            if player in team.get_members():
                team.remove_member(player)
                break
        target_team.add_member(player)
        return target_team

    def assign_leader_to_team(self, leader_id, team_id):
        leader = self.leaders.get(leader_id)
        team = self.teams.get(team_id)
        if not leader or not team:
            return None
        return self.assign_player(leader, team.id)

    def add_bracket(self, bracket: Bracket):
        self.brackets[bracket.id] = bracket
        if bracket.id not in self.bracket_order:
            self.bracket_order.append(bracket.id)
        return bracket

    def create_bracket(self, name, bracket_type=None, description="", output_count=0):
        bracket_cls = BRACKET_CLASS_BY_TYPE.get(bracket_type or BracketType.SWISS.value, Bracket)
        return self.add_bracket(
            bracket_cls(name, bracket_type=bracket_type or bracket_cls.bracket_type_name, description=description, output_count=output_count)
        )

    def update_bracket(self, bracket_id, *, name=None, bracket_type=None, description=None, output_count=None):
        bracket = self.brackets.get(bracket_id)
        if not bracket:
            return None
        if name:
            bracket.name = name
        if bracket_type is not None:
            bracket_cls = BRACKET_CLASS_BY_TYPE.get(bracket_type, Bracket)
            if not isinstance(bracket, bracket_cls):
                updated = bracket_cls(
                    bracket.name,
                    bracket_id=bracket.id,
                    bracket_type=bracket_type,
                    description=bracket.description,
                    output_count=bracket.output_count,
                    outputs=bracket.outputs,
                    standings=bracket.standings,
                    matches=bracket.matches,
                    seed_order=bracket.seed_order,
                )
                updated.ideas = bracket.ideas
                self.brackets[bracket_id] = updated
                bracket = updated
            else:
                bracket.type = bracket_type
        if description is not None:
            bracket.description = description
        if output_count is not None:
            bracket.set_output_count(output_count)
        return bracket

    def bracket_output_view(self, bracket: Bracket):
        bracket.ensure_outputs()
        output_items = []
        for entry in bracket.outputs:
            slot = int(entry.get("slot", 0) or 0)
            resolved_id = entry.get("idea_id")
            resolved_idea = self.ideas.get(resolved_id) if resolved_id else None
            output_items.append(
                {
                    "slot": slot,
                    "label": bracket.output_label(slot),
                    "resolved_idea_id": resolved_id,
                    "resolved_idea_title": resolved_idea.title if resolved_idea else None,
                }
            )
        return output_items

    def clone_output_to_bracket(self, source_bracket_id, slot, target_bracket_id):
        source = self.brackets.get(source_bracket_id)
        target = self.brackets.get(target_bracket_id)
        if not source or not target:
            return None
        source.ensure_outputs()
        slot_num = int(slot or 0)
        if slot_num <= 0 or slot_num > len(source.outputs):
            return None

        resolved_idea_id = source.outputs[slot_num - 1].get("idea_id")
        resolved_idea = self.ideas.get(resolved_idea_id) if resolved_idea_id else None
        title = resolved_idea.title if resolved_idea else source.output_label(slot_num)
        description = f"Output placeholder from {source.name} (slot {slot_num})."
        new_idea = Idea(title, description, category="General")
        new_idea.is_output_clone = True
        new_idea.output_source_bracket_id = source.id
        new_idea.output_slot = slot_num
        new_idea.output_resolved_idea_id = resolved_idea_id
        self.new_idea(new_idea)
        self.move_idea_to_bracket(new_idea.id, target.id)
        return new_idea

    def create_custom_matchup(self, name, description, left_idea_id, right_idea_id):
        if not left_idea_id or not right_idea_id:
            return None
        left = self.get_idea(left_idea_id)
        right = self.get_idea(right_idea_id)
        if not left or not right:
            return None

        bracket_name = (name or "Custom matchup").strip() or "Custom matchup"
        bracket = self.create_bracket(
            bracket_name,
            bracket_type=BracketType.SINGLE_ELIMINATION.value,
            description=(description or "").strip(),
            output_count=2,
        )

        left_clone = self.create_idea(f"{left.title} (custom)", left.description, category=left.category)
        right_clone = self.create_idea(f"{right.title} (custom)", right.description, category=right.category)
        self.move_idea_to_bracket(left_clone.id, bracket.id)
        self.move_idea_to_bracket(right_clone.id, bracket.id)

        matchup = Matchup(
            left_clone.id,
            right_clone.id,
            name=bracket_name,
            description=(description or "").strip(),
            bracket_id=bracket.id,
            is_custom=True,
        )
        bracket.matchups = [matchup]
        self._enter_pairing_stage(force_rebuild=True, reset_roles=False)
        return bracket

    def set_bracket_seed_order(self, bracket_id, ordered_idea_ids):
        bracket = self.brackets.get(bracket_id)
        if not bracket:
            return None
        allowed = {idea.id for idea in bracket.ideas}
        ordered = [idea_id for idea_id in ordered_idea_ids if idea_id in allowed]
        remaining = [idea.id for idea in bracket.ideas if idea.id not in ordered]
        next_seed_order = [*ordered, *remaining]
        changed = next_seed_order != list(bracket.seed_order)
        bracket.seed_order = next_seed_order

        if changed:
            bracket.matches = []
            bracket.matchups = []
            for idea in bracket.ideas:
                bracket.standings[idea.id] = {
                    "played": 0,
                    "won": 0,
                    "lost": 0,
                    "tied": 0,
                    "points": 0,
                    "eliminations": 0,
                    "score_for": 0,
                    "score_against": 0,
                }
            self._enter_pairing_stage(force_rebuild=True, reset_roles=False)
        return bracket.seed_order

    def unresolved_output_dependencies(self, bracket: Bracket):
        blockers = {}
        for idea in bracket.ideas:
            if not getattr(idea, "is_output_clone", False):
                continue
            source_id = getattr(idea, "output_source_bracket_id", None)
            slot = getattr(idea, "output_slot", None)
            if not source_id or not slot:
                continue
            source = self.brackets.get(source_id)
            if not source:
                continue
            source.ensure_outputs()
            slot_index = int(slot) - 1
            resolved = None
            if 0 <= slot_index < len(source.outputs):
                resolved = source.outputs[slot_index].get("idea_id")
            if not resolved:
                blockers.setdefault(source_id, set()).add(int(slot))
        return blockers

    def standings_bracket_views(self):
        brackets = self.ordered_brackets()
        views = []
        for bracket in brackets:
            blockers = self.unresolved_output_dependencies(bracket)
            views.append(
                {
                    "bracket": bracket,
                    "blockers": blockers,
                    "is_ready": not blockers,
                    "pending_rounds": len(bracket.next_pairings()),
                }
            )

        def sort_key(item):
            blocker_count = sum(len(slots) for slots in item["blockers"].values())
            ready_rank = 0 if item["is_ready"] else 1
            return (ready_rank, blocker_count, item["pending_rounds"], item["bracket"].name.lower())

        return sorted(views, key=sort_key)

    def bracket_preview(self, bracket: Bracket):
        seed_ids = [idea_id for idea_id in bracket.seed_order if idea_id in {idea.id for idea in bracket.ideas}]
        for idea in bracket.ideas:
            if idea.id not in seed_ids:
                seed_ids.append(idea.id)

        seed_labels = [self.ideas[idea_id].title for idea_id in seed_ids if idea_id in self.ideas]
        if bracket.type in {BracketType.SINGLE_ELIMINATION.value, BracketType.DOUBLE_ELIMINATION.value}:
            lines = []
            current = [f"Seed {idx+1}: {name}" for idx, name in enumerate(seed_labels)]
            round_no = 1
            while len(current) > 1:
                lines.append(f"Round {round_no}")
                nxt = []
                i = 0
                while i < len(current):
                    if i + 1 < len(current):
                        left = current[i]
                        right = current[i + 1]
                        lines.append(f"  {left}  vs  {right}")
                        nxt.append(f"Winner of ({left} vs {right})")
                    else:
                        lines.append(f"  {current[i]} (bye)")
                        nxt.append(current[i])
                    i += 2
                current = nxt
                round_no += 1
            return {"seed_labels": seed_labels, "lines": lines}

        if bracket.type in {BracketType.ROUND_ROBIN.value, BracketType.SWISS.value}:
            pairings = bracket.next_pairings()
            lines = []
            for idx, pairing in enumerate(pairings[:8]):
                ids = pairing.idea_ids if isinstance(pairing, Matchup) else pairing.get("idea_ids", [])
                if len(ids) == 2:
                    left = self.ideas.get(ids[0]).title if ids[0] in self.ideas else ids[0]
                    right = self.ideas.get(ids[1]).title if ids[1] in self.ideas else ids[1]
                    lines.append(f"Match {idx + 1}: {left} vs {right}")
                elif len(ids) == 1:
                    one = self.ideas.get(ids[0]).title if ids[0] in self.ideas else ids[0]
                    lines.append(f"Match {idx + 1}: {one} (bye)")
            return {"seed_labels": seed_labels, "lines": lines}

        return {"seed_labels": seed_labels, "lines": ["No preview available for this bracket type."]}

    def remove_bracket(self, bracket):
        bracket_id = bracket.id if isinstance(bracket, Bracket) else bracket
        if bracket_id in self.brackets and bracket_id not in {"main"}:
            del self.brackets[bracket_id]
            if bracket_id in self.bracket_order:
                self.bracket_order.remove(bracket_id)

    def reorder_brackets(self, ordered_bracket_ids):
        ordered = [bracket_id for bracket_id in ordered_bracket_ids if bracket_id in self.brackets and bracket_id != "main"]
        self.bracket_order = ["main", *ordered]

    def ordered_bracket_ids(self):
        ordered = [bracket_id for bracket_id in self.bracket_order if bracket_id in self.brackets]
        extras = [bracket_id for bracket_id in self.brackets if bracket_id not in ordered]
        ordered.extend(extras)
        if "main" in self.brackets and (not ordered or ordered[0] != "main"):
            ordered = ["main", *[bracket_id for bracket_id in ordered if bracket_id != "main"]]
        return ordered

    def ordered_brackets(self):
        return [self.brackets[bracket_id] for bracket_id in self.ordered_bracket_ids()]

    def new_idea(self, idea: Idea):
        self.ideas[idea.id] = idea
        self.brackets["main"].add_idea(idea)
        return idea

    def ensure_category(self, name, color=None):
        normalized = (name or "General").strip() or "General"
        if normalized not in self.categories:
            self.categories[normalized] = color or "#38bdf8"
        elif color:
            self.categories[normalized] = color
        return normalized

    def rename_category(self, old_name, new_name, color=None):
        old_name = (old_name or "").strip()
        new_name = (new_name or "").strip()
        if not old_name or not new_name:
            return None
        current_color = self.categories.get(old_name, "#38bdf8")
        target_color = color or current_color
        for idea in self.ideas.values():
            if idea.category == old_name:
                idea.category = new_name
        if old_name in self.categories:
            del self.categories[old_name]
        self.categories[new_name] = target_color
        return new_name

    def resolve_idea_team_id(self, assigned_team_id=None, assigned_leader_id=None):
        if assigned_leader_id:
            team = self.team_for_leader_id(assigned_leader_id)
            if team:
                return team.id
        if assigned_team_id and assigned_team_id in self.teams:
            return assigned_team_id
        return None

    def team_ideas(self, team_id):
        if not team_id:
            return []
        return [idea for idea in self.ideas_sorted(sort_by="submitted", descending=False) if idea.assigned_team_id == team_id]

    def volunteer_submitter(self, leader_id, volunteer=True):
        if volunteer:
            self.submitter_volunteers[leader_id] = time.time()
        else:
            self.submitter_volunteers.pop(leader_id, None)

    def select_team_submitter(self, team_id, leader_id):
        team = self.teams.get(team_id)
        leader = self.leaders.get(leader_id)
        if not team or not leader:
            return False
        if leader.team_id != team.id:
            return False
        self.team_submitters[team.id] = leader.id
        self.volunteer_submitter(leader.id, volunteer=False)
        return True

    def is_team_submitter(self, leader_id):
        return leader_id in self.team_submitters.values()

    def can_leader_submit_ideas(self, leader: Leader):
        if not leader or self.is_paused:
            return False
        if self.stage == "team-leads-ideas":
            if not leader.team_id or leader.team_id == "unassigned":
                return False
            return self.team_submitters.get(leader.team_id) == leader.id
        if self.stage == "all-ideas":
            return bool(leader.team_id and leader.team_id != "unassigned")
        return False

    def submit_idea_for_leader(self, leader: Leader, title, description):
        if not self.can_leader_submit_ideas(leader):
            return None
        return self.create_idea(
            title,
            description,
            assigned_team_id=leader.team_id,
            assigned_leader_id=leader.id,
            category="General",
        )

    def _enter_pairing_stage(self, *, force_rebuild=False, reset_roles=False):
        existing_matchups = self.pairing_round.get("matchups", [])
        if existing_matchups and not force_rebuild:
            return

        idea_ids = [idea.id for idea in self.ideas_sorted(sort_by="submitted", descending=False)]
        matchup_objects = []
        for bracket in self.ordered_brackets():
            if not bracket.can_generate_pairings():
                continue
            bracket_matchups = bracket.generate_matchups()
            bracket.matchups = list(bracket_matchups)
            matchup_objects.extend(bracket_matchups)

        if not matchup_objects and idea_ids:
            for i in range(0, len(idea_ids), 2):
                left = idea_ids[i]
                right = idea_ids[i + 1] if i + 1 < len(idea_ids) else None
                matchup_objects.append(Matchup(left, right, bracket_id="main"))

        matchup_objects.sort(key=lambda item: (str(item.bracket_id or ""), int(item.bracket_round or 1), int(item.order or 0), str(item.id)))
        matchups = [matchup.to_dict() for matchup in matchup_objects]

        if reset_roles:
            for idea_id in idea_ids:
                idea = self.ideas.get(idea_id)
                if idea:
                    idea.point = {Site.MIRANDA.value: None, Site.KIRRAWEE.value: None}
                    idea.backup_point = {Site.MIRANDA.value: None, Site.KIRRAWEE.value: None}

        self.pairing_round["matchups"] = matchups
        self.pairing_round["votes"] = {matchup["id"]: {} for matchup in matchups}
        self.pairing_round["point_nominations"] = {matchup["id"]: {} for matchup in matchups}
        self.pairing_round["backup_nominations"] = {matchup["id"]: {} for matchup in matchups}
        self.pairing_round["cooldowns"] = {}
        self.pairing_round["vote_timestamps"] = {matchup["id"]: {} for matchup in matchups}
        self.pairing_round["point_nomination_times"] = {matchup["id"]: {} for matchup in matchups}
        self.pairing_round["results"] = {}
        self.pairing_round["current_matchup_index"] = 0
        self.pairing_round["show_previous_matchups"] = False
        self.pairing_round["show_result"] = False
        self.pairing_round["matchup_started_at"] = time.time() if matchups else None
        self.pairing_round["countdown_paused"] = False
        self.pairing_round["countdown_pause_started_at"] = None
        self.pairing_round["countdown_paused_remaining"] = None

        self._sync_rounds()
        for round_obj in self.rounds:
            round_obj.matchup_ids = []

        for matchup in matchups:
            matchup_id = matchup.get("id")
            if not matchup_id:
                continue
            round_number = int(matchup.get("bracket_round", 1) or 1)
            round_number = max(1, min(round_number, len(self.rounds)))
            target_round = self.round_for_number(round_number)
            if target_round:
                matchup["round_id"] = target_round.id
                matchup["bracket_round"] = target_round.number
                target_round.add_matchup(matchup_id)

        if matchups and not any(round_obj.matchup_ids for round_obj in self.rounds):
            first_round = self.round_for_number(1)
            if first_round:
                first_round.matchup_ids = [matchup.get("id") for matchup in matchups if matchup.get("id")]

    def current_matchup(self):
        """Get the current active matchup for users to vote on."""
        matchups = self.active_round_matchups()
        index = self.pairing_round.get("current_matchup_index", 0)
        if 0 <= index < len(matchups):
            return matchups[index]
        return None

    def active_round_matchups(self):
        self._sync_rounds()
        matchup_map = {matchup.get("id"): matchup for matchup in self.pairing_round.get("matchups", [])}
        round_obj = self.round_for_number(self.current_round_number())
        if round_obj and round_obj.matchup_ids:
            return [matchup_map[mid] for mid in round_obj.matchup_ids if mid in matchup_map]
        return list(self.pairing_round.get("matchups", []))

    def next_matchup(self):
        """Advance to the next matchup (used by master to move forward in voting)."""
        matchups = self.active_round_matchups()
        index = self.pairing_round.get("current_matchup_index", 0)
        current = self.current_matchup()
        if current:
            self.finalize_matchup_result(current.get("id"))
        if index + 1 < len(matchups):
            self.pairing_round["current_matchup_index"] = index + 1
            self.set_matchup_started_now()
            return True
        return False

    def previous_matchup(self):
        """Go back to the previous matchup (used by master)."""
        index = self.pairing_round.get("current_matchup_index", 0)
        if index > 0:
            self.pairing_round["current_matchup_index"] = index - 1
            self.set_matchup_started_now()
            return True
        return False

    def toggle_show_previous_matchups(self):
        """Toggle visibility of completed matchups on master screen."""
        self.pairing_round["show_previous_matchups"] = not self.pairing_round.get("show_previous_matchups", False)
        return self.pairing_round["show_previous_matchups"]

    def reset_current_stage(self):
        """Reset data for the currently selected stage only."""
        if self.is_round_stage():
            # explicit reset requested by master
            self._enter_pairing_stage(force_rebuild=True, reset_roles=True)
            self.message = "Round stage reset."
            return True
        if self.stage == "team-leads-ideas":
            self.team_submitters = {}
            self.submitter_volunteers = {}
            self.message = "Submitter selection reset."
            return True
        return False

    def _on_stage_changed(self):
        if self.stage == "team-leads-ideas":
            valid_team_ids = {team.id for team in self.ordered_teams() if team.id != "unassigned"}
            self.team_submitters = {team_id: leader_id for team_id, leader_id in self.team_submitters.items() if team_id in valid_team_ids and leader_id in self.leaders}
            self.submitter_volunteers = {leader_id: ts for leader_id, ts in self.submitter_volunteers.items() if leader_id in self.leaders}
        if self.is_round_stage() or self.is_prepare_stage():
            # Do not wipe existing pairing progress when navigating stages.
            self._enter_pairing_stage(force_rebuild=False, reset_roles=False)
            self.pairing_round["current_matchup_index"] = 0
            self.set_matchup_started_now()

    def _matchup_by_id(self, matchup_id):
        return next((matchup for matchup in self.pairing_round.get("matchups", []) if matchup.get("id") == matchup_id), None)

    def cast_vote(self, matchup_id, idea_id, leader_id):
        matchup = self._matchup_by_id(matchup_id)
        if not self.is_round_stage() or not matchup:
            return False
        if idea_id not in matchup.get("idea_ids", []):
            return False
        votes = self.pairing_round.setdefault("votes", {}).setdefault(matchup_id, {})
        votes[leader_id] = idea_id
        vote_times = self.pairing_round.setdefault("vote_timestamps", {}).setdefault(matchup_id, {})
        if idea_id not in vote_times:
            vote_times[idea_id] = time.time()
        return True

    def _site_cooldown_key(self, matchup_id, site):
        return f"{matchup_id}:{site}"

    def cooldown_remaining(self, matchup_id, site):
        until = self.pairing_round.get("cooldowns", {}).get(self._site_cooldown_key(matchup_id, site), 0)
        return max(0, round(until - time.time(), 2))

    def cooldown_until(self, matchup_id, site):
        return float(self.pairing_round.get("cooldowns", {}).get(self._site_cooldown_key(matchup_id, site), 0) or 0)

    def _idea_in_matchup(self, matchup, idea_id):
        if not matchup:
            return None
        if idea_id not in matchup.get("idea_ids", []):
            return None
        return self.ideas.get(idea_id)

    def _leader_is_point_in_idea_site(self, idea, site, leader_id):
        """Check if leader is already the point person for this specific idea and site."""
        return idea.point.get(site) == leader_id

    def nominate_point_role(self, matchup_id, idea_id, leader: Leader, role="point"):
        matchup = self._matchup_by_id(matchup_id)
        if not self.is_round_stage() or not matchup or not leader or not leader.site:
            return False, "Unavailable in current stage."
        idea = self._idea_in_matchup(matchup, idea_id)
        if not idea:
            return False, "Invalid idea selection."
        site = leader.site
        cooldown_left = self.cooldown_remaining(matchup_id, site)
        if cooldown_left > 0:
            return False, f"Wait {cooldown_left:.1f}s before nominating again."

        if role == "point":
            if idea.point.get(site):
                return False, "A point person is already nominated for this site."
            idea.point[site] = leader.id
            nomination_times = self.pairing_round.setdefault("point_nomination_times", {}).setdefault(matchup_id, {}).setdefault(idea_id, {})
            if site not in nomination_times:
                nomination_times[site] = time.time()
        else:
            if not idea.point.get(site):
                return False, "Nominate point first for this site."
            if self._leader_is_point_in_idea_site(idea, site, leader.id):
                return False, "You cannot be both point and backup for the same idea."
            if str(leader.type or "").lower() != LeaderType.ADULT.value.lower():
                return False, "Only adults can nominate as backup point."
            if idea.backup_point.get(site):
                return False, "A backup point is already nominated for this site."
            idea.backup_point[site] = leader.id

        self.pairing_round.setdefault("cooldowns", {})[self._site_cooldown_key(matchup_id, site)] = time.time() + self.NOMINATION_COOLDOWN_SECONDS
        return True, None

    def opt_out_nomination(self, matchup_id, idea_id, leader: Leader):
        matchup = self._matchup_by_id(matchup_id)
        if not self.is_round_stage() or not matchup or not leader or not leader.site:
            return False, "Unavailable in current stage."
        idea = self._idea_in_matchup(matchup, idea_id)
        if not idea:
            return False, "Invalid idea selection."

        site = leader.site

        if idea.point.get(site) == leader.id:
            idea.point[site] = None
            point_times = self.pairing_round.setdefault("point_nomination_times", {}).setdefault(matchup_id, {}).setdefault(idea.id, {})
            point_times.pop(site, None)
            if idea.backup_point.get(site):
                idea.backup_point[site] = None
                self.message = "Point person has opted out."
                return True, "Point person has opted out."
            return True, "You opted out of point."

        if idea.backup_point.get(site) == leader.id:
            idea.backup_point[site] = None
            return True, "You opted out of backup point."

        return False, "You are not nominated for point or backup point."

    def matchup_score_breakdown(self, matchup_id, idea_id):
        """Compute total score for one idea in one matchup.

        Score rule:
        - votes count as-is
        - +3 if point person nominated at any site
        - +2 additional if point person nominated at both sites (so +5 total if both)
        - +1 per backup point person
        """
        matchup = self._matchup_by_id(matchup_id)
        if not matchup or idea_id not in matchup.get("idea_ids", []):
            return None
        idea = self.ideas.get(idea_id)
        if not idea:
            return None

        votes = self.pairing_round.get("votes", {}).get(matchup_id, {})
        vote_count = sum(1 for selected in votes.values() if selected == idea_id)
        point_m = 1 if idea.point.get(Site.MIRANDA.value) else 0
        point_k = 1 if idea.point.get(Site.KIRRAWEE.value) else 0
        backup_m = 1 if idea.backup_point.get(Site.MIRANDA.value) else 0
        backup_k = 1 if idea.backup_point.get(Site.KIRRAWEE.value) else 0

        # +3 if point at any site, +2 additional if point at both sites
        point_score = 0
        if point_m or point_k:
            point_score = 3
            if point_m and point_k:
                point_score = 5
        
        total = vote_count + point_score + backup_m + backup_k
        return {
            "votes": vote_count,
            "point_m": point_m,
            "point_k": point_k,
            "point_score": point_score,
            "backup_m": backup_m,
            "backup_k": backup_k,
            "total": total,
        }

    def _first_point_nomination_time(self, matchup_id, idea_id):
        times = self.pairing_round.get("point_nomination_times", {}).get(matchup_id, {}).get(idea_id, {})
        if not times:
            return None
        return min(times.values())

    def _first_vote_time(self, matchup_id, idea_id):
        return self.pairing_round.get("vote_timestamps", {}).get(matchup_id, {}).get(idea_id)

    def resolve_matchup_winner(self, matchup_id):
        matchup = self._matchup_by_id(matchup_id)
        if not matchup:
            return None
        idea_ids = list(matchup.get("idea_ids", []))
        if not idea_ids:
            return None
        if len(idea_ids) == 1:
            return {
                "matchup_id": matchup_id,
                "idea_ids": idea_ids,
                "scores": {idea_ids[0]: 0},
                "winner_id": idea_ids[0],
                "tie": False,
                "reason": "bye",
            }

        score_map = {}
        breakdowns = {}
        for idea_id in idea_ids:
            breakdown = self.matchup_score_breakdown(matchup_id, idea_id) or {"total": 0}
            breakdowns[idea_id] = breakdown
            score_map[idea_id] = int(breakdown.get("total", 0))

        top_score = max(score_map.values())
        leaders = [idea_id for idea_id, score in score_map.items() if score == top_score]
        if len(leaders) == 1:
            return {
                "matchup_id": matchup_id,
                "idea_ids": idea_ids,
                "scores": score_map,
                "winner_id": leaders[0],
                "tie": False,
                "reason": "score",
            }

        def has_point(idea_id):
            idea = self.ideas.get(idea_id)
            return bool(idea and (idea.point.get(Site.MIRANDA.value) or idea.point.get(Site.KIRRAWEE.value)))

        def has_backup(idea_id):
            idea = self.ideas.get(idea_id)
            return bool(idea and (idea.backup_point.get(Site.MIRANDA.value) or idea.backup_point.get(Site.KIRRAWEE.value)))

        with_point = [idea_id for idea_id in leaders if has_point(idea_id)]
        if len(with_point) == 1:
            return {
                "matchup_id": matchup_id,
                "idea_ids": idea_ids,
                "scores": score_map,
                "winner_id": with_point[0],
                "tie": False,
                "reason": "point-person-tiebreak",
            }
        if len(with_point) == 2:
            with_backup = [idea_id for idea_id in with_point if has_backup(idea_id)]
            if len(with_backup) == 1:
                return {
                    "matchup_id": matchup_id,
                    "idea_ids": idea_ids,
                    "scores": score_map,
                    "winner_id": with_backup[0],
                    "tie": False,
                    "reason": "backup-point-tiebreak",
                }

            point_times = [(idea_id, self._first_point_nomination_time(matchup_id, idea_id)) for idea_id in with_point]
            known_times = [pair for pair in point_times if pair[1] is not None]
            if known_times:
                known_times.sort(key=lambda pair: pair[1])
                return {
                    "matchup_id": matchup_id,
                    "idea_ids": idea_ids,
                    "scores": score_map,
                    "winner_id": known_times[0][0],
                    "tie": False,
                    "reason": "first-point-nomination-tiebreak",
                }

        no_point = [idea_id for idea_id in leaders if not has_point(idea_id)]
        if len(no_point) >= 2:
            vote_times = [(idea_id, self._first_vote_time(matchup_id, idea_id)) for idea_id in no_point]
            known_vote_times = [pair for pair in vote_times if pair[1] is not None]
            if known_vote_times:
                known_vote_times.sort(key=lambda pair: pair[1])
                return {
                    "matchup_id": matchup_id,
                    "idea_ids": idea_ids,
                    "scores": score_map,
                    "winner_id": known_vote_times[0][0],
                    "tie": False,
                    "reason": "first-vote-tiebreak",
                }

        # Only allow a true tie for round-robin and swiss styles.
        bracket = self.get_bracket(self.ideas.get(idea_ids[0]).bracket_id) if self.ideas.get(idea_ids[0]) else None
        tie_allowed = bool(bracket and bracket.type in {BracketType.ROUND_ROBIN.value, BracketType.SWISS.value})
        if tie_allowed:
            return {
                "matchup_id": matchup_id,
                "idea_ids": idea_ids,
                "scores": score_map,
                "winner_id": None,
                "tie": True,
                "reason": "draw",
            }

        # deterministic fallback for elimination brackets
        ordered = sorted(leaders)
        return {
            "matchup_id": matchup_id,
            "idea_ids": idea_ids,
            "scores": score_map,
            "winner_id": ordered[0],
            "tie": False,
            "reason": "deterministic-fallback",
        }

    def finalize_matchup_result(self, matchup_id):
        result = self.resolve_matchup_winner(matchup_id)
        if not result:
            return None
        self.pairing_round.setdefault("results", {})[matchup_id] = result

        idea_ids = result.get("idea_ids", [])
        if idea_ids:
            first_idea = self.ideas.get(idea_ids[0])
            bracket = self.get_bracket(first_idea.bracket_id) if first_idea else None
            if bracket and len(idea_ids) <= 2:
                bracket.record_match(result)

        return result

    def _display_label_for_matchup(self, matchup, ideas, bracket_name, bracket_round):
        left = ideas[0]["title"] if len(ideas) > 0 else (matchup.get("left_label") or "TBD")
        right = ideas[1]["title"] if len(ideas) > 1 else (matchup.get("right_label") or "TBD")
        return f"{bracket_name}, Round {bracket_round}: {left} vs {right}"

    def _matchups_display_from(self, matchups):
        display = []
        for matchup in matchups:
            matchup_id = matchup.get("id")
            idea_ids = matchup.get("idea_ids", [])
            bracket_id = matchup.get("bracket_id")
            bracket = self.get_bracket(bracket_id)
            bracket_name = bracket.name if bracket else "Bracket"
            bracket_round = int(matchup.get("bracket_round", 1) or 1)
            votes = self.pairing_round.get("votes", {}).get(matchup_id, {})
            ideas = []
            for idea_id in idea_ids:
                idea = self.ideas.get(idea_id)
                if not idea:
                    continue
                vote_count = sum(1 for selected in votes.values() if selected == idea_id)
                nominations = []
                for site in [Site.MIRANDA.value, Site.KIRRAWEE.value]:
                    if idea.point.get(site):
                        nominations.append({"site": site, "role": "point", "name": self.leaders.get(idea.point.get(site)).name if idea.point.get(site) in self.leaders else idea.point.get(site)})
                    if idea.backup_point.get(site):
                        nominations.append({"site": site, "role": "backup point", "name": self.leaders.get(idea.backup_point.get(site)).name if idea.backup_point.get(site) in self.leaders else idea.backup_point.get(site)})
                ideas.append(
                    {
                        "id": idea.id,
                        "title": idea.title,
                        "description": idea.description,
                        "votes": vote_count,
                        "score": self.matchup_score_breakdown(matchup_id, idea_id)["total"] if self.matchup_score_breakdown(matchup_id, idea_id) else vote_count,
                        "point_ids": dict(idea.point),
                        "backup_ids": dict(idea.backup_point),
                        "nominations": nominations,
                        "point": {
                            site: self.leaders.get(idea.point.get(site)).name if idea.point.get(site) in self.leaders else (idea.point.get(site) or None)
                            for site in [Site.MIRANDA.value, Site.KIRRAWEE.value]
                        },
                        "backup": {
                            site: self.leaders.get(idea.backup_point.get(site)).name if idea.backup_point.get(site) in self.leaders else (idea.backup_point.get(site) or None)
                            for site in [Site.MIRANDA.value, Site.KIRRAWEE.value]
                        },
                    }
                )
            sites = [Site.MIRANDA.value, Site.KIRRAWEE.value]
            display.append(
                {
                    "id": matchup_id,
                    "bracket_id": bracket_id,
                    "bracket_name": bracket_name,
                    "bracket_round": bracket_round,
                    "name": matchup.get("name") or "",
                    "display_label": self._display_label_for_matchup(matchup, ideas, bracket_name, bracket_round),
                    "ideas": ideas,
                    "result": self.resolve_matchup_winner(matchup_id),
                    "cooldowns": {site: self.cooldown_remaining(matchup_id, site) for site in sites},
                    "cooldown_untils": {site: self.cooldown_until(matchup_id, site) for site in sites},
                }
            )
        return display

    def pairing_matchups_display(self):
        return self._matchups_display_from(self.pairing_round.get("matchups", []))

    def active_round_matchups_display(self):
        return self._matchups_display_from(self.active_round_matchups())

    def create_idea(self, title, description, assigned_team_id=None, assigned_leader_id=None, category="General"):
        category_name = self.ensure_category(category)
        resolved_team_id = self.resolve_idea_team_id(assigned_team_id, assigned_leader_id)
        return self.new_idea(
            Idea(
                title,
                description,
                assigned_team_id=resolved_team_id,
                assigned_leader_id=assigned_leader_id,
                category=category_name,
            )
        )

    def update_idea(self, idea_id, *, title=None, description=None, bracket_id=None, category=None, assigned_team_id=None, assigned_leader_id=None, point_miranda=None, point_kirrawee=None, backup_miranda=None, backup_kirrawee=None):
        idea = self.ideas.get(idea_id)
        if not idea:
            return None
        if title:
            idea.title = title
        if description is not None:
            idea.description = description
        if category is not None:
            idea.category = self.ensure_category(category)
        if assigned_leader_id is not None:
            idea.assigned_leader_id = assigned_leader_id or None
        if assigned_team_id is not None or assigned_leader_id is not None:
            idea.assigned_team_id = self.resolve_idea_team_id(assigned_team_id, idea.assigned_leader_id)
        if point_miranda is not None:
            idea.point[Site.MIRANDA.value] = point_miranda or None
        if point_kirrawee is not None:
            idea.point[Site.KIRRAWEE.value] = point_kirrawee or None
        if backup_miranda is not None:
            idea.backup_point[Site.MIRANDA.value] = backup_miranda or None
        if backup_kirrawee is not None:
            idea.backup_point[Site.KIRRAWEE.value] = backup_kirrawee or None
        if bracket_id is not None and bracket_id in self.brackets:
            self.move_idea_to_bracket(idea_id, bracket_id)
        return idea
    def assign_idea(self, idea: Idea, bracket_name: str):
        if bracket_name in self.brackets:
            for bracket in self.brackets.values():
                if idea in bracket.ideas:
                    bracket.remove_idea(idea)
                    break
            self.brackets[bracket_name].add_idea(idea)
            return self.brackets[bracket_name]
        return None

    def move_idea_to_bracket(self, idea_id, bracket_id):
        idea = self.ideas.get(idea_id)
        bracket = self.brackets.get(bracket_id)
        if not idea or not bracket:
            return None
        return self.assign_idea(idea, bracket.id)

    def remove_idea(self, idea_id):
        idea = self.ideas.pop(idea_id, None)
        if not idea:
            return
        for bracket in self.brackets.values():
            if idea in bracket.ideas:
                bracket.remove_idea(idea)

    def set_stage(self, stage_index):
        self.current_stage = max(0, min(stage_index, len(self.stage_sequence()) - 1))
        self._on_stage_changed()
        return self.stage

    def advance_stage(self):
        return self.set_stage(self.current_stage + 1)

    def rewind_stage(self):
        return self.set_stage(self.current_stage - 1)

    def add_round(self):
        self.round_count = max(1, int(self.round_count or 1) + 1)
        return self.round_count

    def remove_round(self, round_number=None):
        current_rounds = max(1, int(self.round_count or 1))
        if current_rounds <= 1:
            return current_rounds
        self.round_count = current_rounds - 1
        self.current_stage = min(self.current_stage, len(self.stage_sequence()) - 1)
        return self.round_count

    def auto_fill_round(self):
        self._enter_pairing_stage(force_rebuild=True, reset_roles=False)
        return self.pairing_round.get("matchups", [])

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.is_paused = False

    def get_leader(self, leader_id):
        return self.leaders.get(leader_id)

    def get_team(self, team_id):
        return self.teams.get(team_id)

    def get_bracket(self, bracket_id):
        return self.brackets.get(bracket_id)

    def get_idea(self, idea_id):
        return self.ideas.get(idea_id)

    def team_for_leader(self, leader: Leader):
        if not leader or not leader.team_id:
            return self.teams.get("unassigned")
        return self.teams.get(leader.team_id, self.teams.get("unassigned"))

    def team_name_for_leader(self, leader: Leader):
        team = self.team_for_leader(leader)
        return team.name if team else "Unassigned"

    def leader_sort_key(self, leader: Leader):
        team = self.team_for_leader(leader)
        team_index = self.ordered_team_ids().index(team.id) if team and team.id in self.ordered_team_ids() else 999
        return (team_index, leader.name.lower())

    def sorted_leaders(self):
        return sorted(self.leaders.values(), key=self.leader_sort_key)

    def ideas_sorted(self, sort_by="submitted", descending=True):
        ideas = list(self.ideas.values())

        def idea_team_name(idea: Idea):
            team = self.teams.get(idea.assigned_team_id)
            return team.name if team else "Unassigned"

        key_map = {
            "submitted": lambda idea: idea.created_at or "",
            "category": lambda idea: (idea.category or "").lower(),
            "team": lambda idea: idea_team_name(idea).lower(),
            "title": lambda idea: (idea.title or "").lower(),
        }
        key_func = key_map.get(sort_by, key_map["submitted"])
        ideas.sort(key=key_func, reverse=descending)
        return ideas

    def idea_display(self, idea: Idea):
        assigned_leader = self.leaders.get(idea.assigned_leader_id)
        team = self.teams.get(idea.assigned_team_id)
        bracket = self.brackets.get(idea.bracket_id)
        return {
            **idea.to_dict(),
            "assigned_leader_name": assigned_leader.name if assigned_leader else None,
            "team_name": team.name if team else "Unassigned",
            "bracket_name": bracket.name if bracket else "Main / unassigned",
            "category_color": self.categories.get(idea.category, "#38bdf8"),
            "point_miranda_name": self.leaders.get(idea.point.get(Site.MIRANDA.value)).name if idea.point.get(Site.MIRANDA.value) in self.leaders else (idea.point.get(Site.MIRANDA.value) or None),
            "point_kirrawee_name": self.leaders.get(idea.point.get(Site.KIRRAWEE.value)).name if idea.point.get(Site.KIRRAWEE.value) in self.leaders else (idea.point.get(Site.KIRRAWEE.value) or None),
            "backup_miranda_name": self.leaders.get(idea.backup_point.get(Site.MIRANDA.value)).name if idea.backup_point.get(Site.MIRANDA.value) in self.leaders else (idea.backup_point.get(Site.MIRANDA.value) or None),
            "backup_kirrawee_name": self.leaders.get(idea.backup_point.get(Site.KIRRAWEE.value)).name if idea.backup_point.get(Site.KIRRAWEE.value) in self.leaders else (idea.backup_point.get(Site.KIRRAWEE.value) or None),
        }

    def sync_relationships(self):
        for team in self.teams.values():
            team.members = []
        for leader in self.leaders.values():
            if leader.team_id and leader.team_id in self.teams:
                team = self.teams[leader.team_id]
                if leader not in team.members:
                    team.members.append(leader)
            else:
                self.teams["unassigned"].add_member(leader)

        for bracket in self.brackets.values():
            bracket.ideas = []
        for idea in self.ideas.values():
            if idea.bracket_id and idea.bracket_id in self.brackets:
                self.brackets[idea.bracket_id].ideas.append(idea)
            else:
                self.brackets["main"].add_idea(idea)

        for bracket in self.brackets.values():
            valid_ids = {idea.id for idea in bracket.ideas}
            bracket.ensure_outputs()
            bracket.seed_order = [idea_id for idea_id in bracket.seed_order if idea_id in valid_ids]
            for idea in bracket.ideas:
                bracket.ensure_standing(idea.id)
                if idea.id not in bracket.seed_order:
                    bracket.seed_order.append(idea.id)

    def summary(self):
        team_summaries = [
            {
                "id": team.id,
                "name": team.name,
                "description": team.description,
                "color": team.color,
                "members": [member.to_dict() for member in team.get_members()],
            }
            for team in self.ordered_teams()
        ]
        bracket_summaries = [
            {
                "id": bracket.id,
                "name": bracket.name,
                "type": bracket.type,
                "description": bracket.description,
                "output_count": bracket.output_count,
                "outputs": list(bracket.outputs),
                "ideas": [idea.to_dict() for idea in bracket.get_ideas()],
            }
            for bracket in self.ordered_brackets()
        ]
        return {
            "name": self.name,
            "stage": self.stage,
            "stage_label": self.stage_label(),
            "is_paused": self.is_paused,
            "message": self.message,
            "leader_count": len(self.leaders),
            "team_count": len(self.teams),
            "idea_count": len(self.ideas),
            "bracket_count": len(self.brackets),
            "teams": team_summaries,
            "brackets": bracket_summaries,
            "leaders": [leader.to_dict() for leader in self.sorted_leaders()],
            "ideas": [self.idea_display(idea) for idea in self.ideas_sorted()],
        }

    def to_dict(self):
        return {
            "name": self.name,
            "current_stage": self.current_stage,
            "round_count": self.round_count,
            "is_paused": self.is_paused,
            "message": self.message,
            "team_submitters": dict(self.team_submitters),
            "submitter_volunteers": dict(self.submitter_volunteers),
            "pairing_round": {
                "matchups": list(self.pairing_round.get("matchups", [])),
                "votes": dict(self.pairing_round.get("votes", {})),
                "point_nominations": dict(self.pairing_round.get("point_nominations", {})),
                "backup_nominations": dict(self.pairing_round.get("backup_nominations", {})),
                "cooldowns": dict(self.pairing_round.get("cooldowns", {})),
                "vote_timestamps": dict(self.pairing_round.get("vote_timestamps", {})),
                "point_nomination_times": dict(self.pairing_round.get("point_nomination_times", {})),
                "results": dict(self.pairing_round.get("results", {})),
                "current_matchup_index": self.pairing_round.get("current_matchup_index", 0),
                "show_previous_matchups": self.pairing_round.get("show_previous_matchups", False),
                "show_result": self.pairing_round.get("show_result", False),
                "countdown_seconds": self.pairing_round.get("countdown_seconds", 60),
                "matchup_started_at": self.pairing_round.get("matchup_started_at"),
                "countdown_paused": self.pairing_round.get("countdown_paused", False),
                "countdown_pause_started_at": self.pairing_round.get("countdown_pause_started_at"),
                "countdown_paused_remaining": self.pairing_round.get("countdown_paused_remaining"),
            },
            "team_order": list(self.team_order),
            "bracket_order": list(self.bracket_order),
            "rounds": [round_obj.to_dict() for round_obj in self.rounds],
            "categories": dict(self.categories),
            "teams": [team.to_dict() for team in self.teams.values()],
            "leaders": [leader.to_dict() for leader in self.leaders.values()],
            "brackets": [bracket.to_dict() for bracket in self.brackets.values()],
            "ideas": [idea.to_dict() for idea in self.ideas.values()],
        }

    @classmethod
    def from_dict(cls, data):
        game = cls(data.get("name", "Game"))
        game.current_stage = data.get("current_stage", 0)
        game.round_count = int(data.get("round_count", 1) or 1)
        game.is_paused = data.get("is_paused", False)
        game.message = data.get("message", "Game ready.")
        game.team_submitters = dict(data.get("team_submitters", {}))
        game.submitter_volunteers = dict(data.get("submitter_volunteers", {}))
        game.pairing_round = dict(data.get("pairing_round", game.pairing_round))
        game.pairing_round.pop("strategy", None)
        game.pairing_round.setdefault("matchups", [])
        game.pairing_round.setdefault("votes", {})
        game.pairing_round.setdefault("point_nominations", {})
        game.pairing_round.setdefault("backup_nominations", {})
        game.pairing_round.setdefault("cooldowns", {})
        game.pairing_round.setdefault("vote_timestamps", {})
        game.pairing_round.setdefault("point_nomination_times", {})
        game.pairing_round.setdefault("results", {})
        game.pairing_round.setdefault("current_matchup_index", 0)
        game.pairing_round.setdefault("show_previous_matchups", False)
        game.pairing_round.setdefault("show_result", False)
        game.pairing_round.setdefault("countdown_seconds", 60)
        game.pairing_round.setdefault("matchup_started_at", None)
        game.pairing_round.setdefault("countdown_paused", False)
        game.pairing_round.setdefault("countdown_pause_started_at", None)
        game.pairing_round.setdefault("countdown_paused_remaining", None)
        game.team_order = list(data.get("team_order", []))
        game.bracket_order = list(data.get("bracket_order", []))
        game.rounds = [Round.from_dict(item) for item in data.get("rounds", [])] or [Round(number=1)]
        game.categories = dict(data.get("categories", {"General": "#38bdf8"}))
        game.teams = {team_data["id"]: Team.from_dict(team_data) for team_data in data.get("teams", [])}
        if "unassigned" not in game.teams:
            game.teams["unassigned"] = Team("Unassigned", team_id="unassigned", description="Leaders that have not been assigned to a team yet.", color="#64748b")
        if not game.team_order:
            game.team_order = list(game.teams.keys())
        game.leaders = {leader_data["id"]: Leader.from_dict(leader_data) for leader_data in data.get("leaders", [])}
        game.brackets = {bracket_data["id"]: Bracket.from_dict(bracket_data) for bracket_data in data.get("brackets", [])}
        if "main" not in game.brackets:
            game.brackets["main"] = Bracket("Main Bracket", bracket_id="main", bracket_type=BracketType.SWISS.value, description="The root bracket that receives new ideas.", output_count=0)
        if not game.bracket_order:
            game.bracket_order = list(game.brackets.keys())
        game.ideas = {idea_data["id"]: Idea.from_dict(idea_data) for idea_data in data.get("ideas", [])}
        game.sync_relationships()
        return game