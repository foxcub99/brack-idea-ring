from enum import Enum
from uuid import uuid4

from .idea import Idea


class BracketType(Enum):
    ROUND_ROBIN = "Round Robin"
    SINGLE_ELIMINATION = "Single Elimination"
    DOUBLE_ELIMINATION = "Double Elimination"
    SWISS = "Swiss"
    FEEDER = "Feeder"
    MAIN = "Main"


class Bracket:
    def __init__(self, name, bracket_id=None, bracket_type=None, target_count=None, description="", feeds_into=None):
        self.id = bracket_id or uuid4().hex
        self.name = name
        self.ideas = []
        self.type = bracket_type
        self.target_count = target_count
        self.description = description
        self.feeds_into = list(feeds_into or [])

    def add_idea(self, idea: Idea):
        if idea not in self.ideas:
            self.ideas.append(idea)
        idea.bracket_id = self.id

    def remove_idea(self, idea: Idea):
        if idea in self.ideas:
            self.ideas.remove(idea)
        if idea.bracket_id == self.id:
            idea.bracket_id = None

    def get_ideas(self):
        return self.ideas

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "target_count": self.target_count,
            "description": self.description,
            "feeds_into": list(self.feeds_into),
            "idea_ids": [idea.id for idea in self.ideas],
        }

    @classmethod
    def from_dict(cls, data):
        bracket = cls(
            data.get("name", ""),
            bracket_id=data.get("id"),
            bracket_type=data.get("type"),
            target_count=data.get("target_count"),
            description=data.get("description", ""),
            feeds_into=data.get("feeds_into", []),
        )
        bracket.idea_ids = list(data.get("idea_ids", []))
        return bracket

