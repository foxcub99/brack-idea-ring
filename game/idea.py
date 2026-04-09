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
        self.backup_point = {Site.MIRANDA.value: None, Site.KIRRAWEE.value: None}
        self.assigned_team_id = assigned_team_id
        self.assigned_leader_id = assigned_leader_id
        self.bracket_id = bracket_id
        self.is_output_clone = False
        self.output_source_bracket_id = None
        self.output_slot = None
        self.output_resolved_idea_id = None
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "point": dict(self.point),
            "backup_point": dict(self.backup_point),
            "assigned_team_id": self.assigned_team_id,
            "assigned_leader_id": self.assigned_leader_id,
            "bracket_id": self.bracket_id,
            "is_output_clone": self.is_output_clone,
            "output_source_bracket_id": self.output_source_bracket_id,
            "output_slot": self.output_slot,
            "output_resolved_idea_id": self.output_resolved_idea_id,
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
        idea.backup_point = dict(data.get("backup_point", idea.backup_point))
        idea.is_output_clone = bool(data.get("is_output_clone", False))
        idea.output_source_bracket_id = data.get("output_source_bracket_id")
        idea.output_slot = data.get("output_slot")
        idea.output_resolved_idea_id = data.get("output_resolved_idea_id")
        return idea

    def __str__(self):
        return f"Idea: {self.title}\nDescription: {self.description}"