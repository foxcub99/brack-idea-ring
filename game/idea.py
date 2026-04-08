from datetime import datetime, timezone
from uuid import uuid4

from .leader import Site


class Idea:
    def __init__(self, title, description, idea_id=None, assigned_team_id=None, assigned_leader_id=None, bracket_id=None, category="General", created_at=None):
        self.id = idea_id or uuid4().hex
        self.title = title
        self.description = description
        self.category = category
        self.point = {Site.MIRANDA.value: None, Site.KIRRAWEE.value: None}
        self.backupPoint = {Site.MIRANDA.value: None, Site.KIRRAWEE.value: None}
        self.rawScore = 0
        self.assigned_team_id = assigned_team_id
        self.assigned_leader_id = assigned_leader_id
        self.bracket_id = bracket_id
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "point": dict(self.point),
            "backupPoint": dict(self.backupPoint),
            "rawScore": self.rawScore,
            "assigned_team_id": self.assigned_team_id,
            "assigned_leader_id": self.assigned_leader_id,
            "bracket_id": self.bracket_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data):
        idea = cls(
            data.get("title", ""),
            data.get("description", ""),
            idea_id=data.get("id"),
            assigned_team_id=data.get("assigned_team_id") or data.get("team_id"),
            assigned_leader_id=data.get("assigned_leader_id") or data.get("created_by_id"),
            bracket_id=data.get("bracket_id"),
            category=data.get("category", "General"),
            created_at=data.get("created_at"),
        )
        idea.point = dict(data.get("point", idea.point))
        idea.backupPoint = dict(data.get("backupPoint", idea.backupPoint))
        idea.rawScore = data.get("rawScore", 0)
        return idea

    def __str__(self):
        return f"Idea: {self.title}\nDescription: {self.description}"