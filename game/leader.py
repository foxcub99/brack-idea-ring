from enum import Enum
from uuid import uuid4


class LeaderType(Enum):
    ADULT = "Adult"
    LITE = "Lite"


class Site(Enum):
    MIRANDA = "Miranda"
    KIRRAWEE = "Kirrawee"


class Leader:
    def __init__(self, name, leader_id=None, leader_type=None, site=None, team_id=None, can_submit_ideas=False):
        self.id = leader_id or uuid4().hex
        self.name = name
        self.type = leader_type
        self.site = site
        self.team_id = team_id
        self.can_submit_ideas = can_submit_ideas

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "site": self.site,
            "team_id": self.team_id,
            "can_submit_ideas": self.can_submit_ideas,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            data.get("name", ""),
            leader_id=data.get("id"),
            leader_type=data.get("type"),
            site=data.get("site"),
            team_id=data.get("team_id"),
            can_submit_ideas=data.get("can_submit_ideas", False),
        )

    def __str__(self):
        return f"{self.name}"