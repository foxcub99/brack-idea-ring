from leader import Leader
from team import Team
from bracket import Bracket
from idea import Idea

class Game:
    def __init__(self, name):
        self.name = name
        self.teams = {}
        self.teams["unassigned"] = Team("Unassigned")
        self.brackets = {}
        self.brackets["main"] = Bracket("Main Bracket")

    def add_team(self, team: Team):
        self.teams[team.name] = team

    def remove_team(self, team: Team):
        if team.name in self.teams:
            del self.teams[team.name]

    def new_player(self, player: Leader):
        self.teams["unassigned"].add_member(player)
        
    def assign_player(self, player: Leader, team_name: str):
        if team_name in self.teams:
            # Remove player from current team
            for team in self.teams.values():
                if player in team.get_members():
                    team.remove_member(player)
                    break
            # Add player to new team
            self.teams[team_name].add_member(player)
            
    def add_bracket(self, bracket: Bracket):
        self.brackets[bracket.name] = bracket
        
    def remove_bracket(self, bracket: Bracket):
        if bracket.name in self.brackets:
            del self.brackets[bracket.name]
            
    def new_idea(self, idea: Idea):
        self.brackets["main"].ideas.append(idea)
        
    def assign_idea(self, idea: Idea, bracket_name: str):
        if bracket_name in self.brackets:
            # Remove idea from current bracket
            for bracket in self.brackets.values():
                if idea in bracket.ideas:
                    bracket.ideas.remove(idea)
                    break
            # Add idea to new bracket
            self.brackets[bracket_name].ideas.append(idea)