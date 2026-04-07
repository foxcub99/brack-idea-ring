from uuid import uuid4

from .leader import Site


class Idea:
    def __init__(self, title, description, idea_id=None, created_by_id=None, bracket_id=None, status="draft"):
        self.id = idea_id or uuid4().hex
        self.title = title
        self.description = description
        self.point = {Site.MIRANDA.value: None, Site.KIRRAWEE.value: None}
        self.backupPoint = {Site.MIRANDA.value: None, Site.KIRRAWEE.value: None}
        self.rawScore = 0
        self.created_by_id = created_by_id
        self.bracket_id = bracket_id
        self.status = status

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "point": dict(self.point),
            "backupPoint": dict(self.backupPoint),
            "rawScore": self.rawScore,
            "created_by_id": self.created_by_id,
            "bracket_id": self.bracket_id,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data):
        idea = cls(
            data.get("title", ""),
            data.get("description", ""),
            idea_id=data.get("id"),
            created_by_id=data.get("created_by_id"),
            bracket_id=data.get("bracket_id"),
            status=data.get("status", "draft"),
        )
        idea.point = dict(data.get("point", idea.point))
        idea.backupPoint = dict(data.get("backupPoint", idea.backupPoint))
        idea.rawScore = data.get("rawScore", 0)
        return idea

    def __str__(self):
        return f"Idea: {self.title}\nDescription: {self.description}"