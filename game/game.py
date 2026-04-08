from __future__ import annotations

from .bracket import Bracket, BracketType
from .idea import Idea
from .leader import Leader, LeaderType, Site
from .team import Team


class Game:
    STAGES = [
        "setup",
        "team-leads-ideas",
        "all-ideas",
        "bracket-sorting",
        "pairing",
        "scoring",
        "complete",
    ]

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
        self.is_paused = False
        self.message = "Game ready."
        self.teams["unassigned"] = Team("Unassigned", team_id="unassigned", description="Leaders that have not been assigned to a team yet.", color="#64748b")
        self.brackets["main"] = Bracket("Main Bracket", bracket_id="main", bracket_type=BracketType.MAIN.value, description="The root bracket that receives new ideas.")
        self.team_order = ["unassigned"]
        self.bracket_order = ["main"]

    @property
    def stage(self):
        return self.STAGES[self.current_stage]

    def stage_label(self):
        return self.stage.replace("-", " ").title()

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

    def create_bracket(self, name, bracket_type=None, target_count=None, description=""):
        return self.add_bracket(
            Bracket(name, bracket_type=bracket_type, target_count=target_count, description=description)
        )

    def update_bracket(self, bracket_id, *, name=None, bracket_type=None, target_count=None, description=None, feeds_into=None):
        bracket = self.brackets.get(bracket_id)
        if not bracket:
            return None
        if name:
            bracket.name = name
        if bracket_type is not None:
            bracket.type = bracket_type
        if target_count is not None:
            bracket.target_count = target_count
        if description is not None:
            bracket.description = description
        if feeds_into is not None:
            bracket.feeds_into = list(feeds_into)
        return bracket

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

    def update_idea(self, idea_id, *, title=None, description=None, bracket_id=None, category=None, assigned_team_id=None, assigned_leader_id=None):
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
        self.current_stage = max(0, min(stage_index, len(self.STAGES) - 1))
        return self.stage

    def advance_stage(self):
        return self.set_stage(self.current_stage + 1)

    def rewind_stage(self):
        return self.set_stage(self.current_stage - 1)

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
                "target_count": bracket.target_count,
                "description": bracket.description,
                "feeds_into": list(bracket.feeds_into),
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
            "is_paused": self.is_paused,
            "message": self.message,
            "team_order": list(self.team_order),
            "bracket_order": list(self.bracket_order),
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
        game.is_paused = data.get("is_paused", False)
        game.message = data.get("message", "Game ready.")
        game.team_order = list(data.get("team_order", []))
        game.bracket_order = list(data.get("bracket_order", []))
        game.categories = dict(data.get("categories", {"General": "#38bdf8"}))
        game.teams = {team_data["id"]: Team.from_dict(team_data) for team_data in data.get("teams", [])}
        if "unassigned" not in game.teams:
            game.teams["unassigned"] = Team("Unassigned", team_id="unassigned", description="Leaders that have not been assigned to a team yet.", color="#64748b")
        if not game.team_order:
            game.team_order = list(game.teams.keys())
        game.leaders = {leader_data["id"]: Leader.from_dict(leader_data) for leader_data in data.get("leaders", [])}
        game.brackets = {bracket_data["id"]: Bracket.from_dict(bracket_data) for bracket_data in data.get("brackets", [])}
        if "main" not in game.brackets:
            game.brackets["main"] = Bracket("Main Bracket", bracket_id="main", bracket_type=BracketType.MAIN.value, description="The root bracket that receives new ideas.")
        if not game.bracket_order:
            game.bracket_order = list(game.brackets.keys())
        game.ideas = {idea_data["id"]: Idea.from_dict(idea_data) for idea_data in data.get("ideas", [])}
        game.sync_relationships()
        return game