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
        self.brackets = {}
        self.leaders = {}
        self.ideas = {}
        self.current_stage = 0
        self.is_paused = False
        self.message = "Game ready."
        self.teams["unassigned"] = Team("Unassigned", team_id="unassigned", description="Leaders that have not been assigned to a team yet.", color="#64748b")
        self.brackets["main"] = Bracket("Main Bracket", bracket_id="main", bracket_type=BracketType.MAIN.value, description="The root bracket that receives new ideas.")

    @property
    def stage(self):
        return self.STAGES[self.current_stage]

    def stage_label(self):
        return self.stage.replace("-", " ").title()

    def add_team(self, team: Team):
        self.teams[team.id] = team
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
            del self.teams[team_id]

    def new_player(self, player: Leader):
        self.leaders[player.id] = player
        self.teams["unassigned"].add_member(player)
        return player

    def create_leader(self, name, leader_type=None, site=None, can_submit_ideas=False):
        leader = Leader(name, leader_type=leader_type, site=site, can_submit_ideas=can_submit_ideas)
        return self.new_player(leader)

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

    def new_idea(self, idea: Idea):
        self.ideas[idea.id] = idea
        self.brackets["main"].add_idea(idea)
        return idea

    def create_idea(self, title, description, created_by_id=None):
        return self.new_idea(Idea(title, description, created_by_id=created_by_id))

    def update_idea(self, idea_id, *, title=None, description=None, status=None, bracket_id=None):
        idea = self.ideas.get(idea_id)
        if not idea:
            return None
        if title:
            idea.title = title
        if description is not None:
            idea.description = description
        if status is not None:
            idea.status = status
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
            for team in self.teams.values()
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
            for bracket in self.brackets.values()
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
            "leaders": [leader.to_dict() for leader in self.leaders.values()],
            "ideas": [idea.to_dict() for idea in self.ideas.values()],
        }

    def to_dict(self):
        return {
            "name": self.name,
            "current_stage": self.current_stage,
            "is_paused": self.is_paused,
            "message": self.message,
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
        game.teams = {team_data["id"]: Team.from_dict(team_data) for team_data in data.get("teams", [])}
        if "unassigned" not in game.teams:
            game.teams["unassigned"] = Team("Unassigned", team_id="unassigned", description="Leaders that have not been assigned to a team yet.", color="#64748b")
        game.leaders = {leader_data["id"]: Leader.from_dict(leader_data) for leader_data in data.get("leaders", [])}
        game.brackets = {bracket_data["id"]: Bracket.from_dict(bracket_data) for bracket_data in data.get("brackets", [])}
        if "main" not in game.brackets:
            game.brackets["main"] = Bracket("Main Bracket", bracket_id="main", bracket_type=BracketType.MAIN.value, description="The root bracket that receives new ideas.")
        game.ideas = {idea_data["id"]: Idea.from_dict(idea_data) for idea_data in data.get("ideas", [])}
        game.sync_relationships()
        return game