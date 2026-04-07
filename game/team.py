from uuid import uuid4

from .leader import Leader


class Team:
    def __init__(self, name, team_id=None, description="", color="#2563eb"):
        self.id = team_id or uuid4().hex
        self.name = name
        self.description = description
        self.color = color
        self.members = []
        self.member_ids = []

    def add_member(self, member: Leader):
        if member.id not in self.member_ids:
            self.member_ids.append(member.id)
        if member not in self.members:
            self.members.append(member)
        member.team_id = self.id

    def remove_member(self, member: Leader):
        if member in self.members:
            self.members.remove(member)
        if member.id in self.member_ids:
            self.member_ids.remove(member.id)
        if member.team_id == self.id:
            member.team_id = None

    def get_members(self):
        return self.members

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "color": self.color,
            "member_ids": list(self.member_ids),
        }

    @classmethod
    def from_dict(cls, data):
        team = cls(
            data.get("name", ""),
            team_id=data.get("id"),
            description=data.get("description", ""),
            color=data.get("color", "#2563eb"),
        )
        team.member_ids = list(data.get("member_ids", []))
        return team