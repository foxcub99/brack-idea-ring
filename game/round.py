from __future__ import annotations

from uuid import uuid4


class Round:
    def __init__(self, name=None, *, round_id=None, number=1, matchup_ids=None):
        self.id = round_id or uuid4().hex
        self.number = int(number or 1)
        self.name = name or f"Round {self.number}"
        self.matchup_ids = list(matchup_ids or [])

    def add_matchup(self, matchup_id):
        if matchup_id and matchup_id not in self.matchup_ids:
            self.matchup_ids.append(matchup_id)

    def remove_matchup(self, matchup_id):
        if matchup_id in self.matchup_ids:
            self.matchup_ids.remove(matchup_id)

    def to_dict(self):
        return {
            "id": self.id,
            "number": self.number,
            "name": self.name,
            "matchup_ids": list(self.matchup_ids),
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            data.get("name"),
            round_id=data.get("id"),
            number=data.get("number", 1),
            matchup_ids=data.get("matchup_ids", []),
        )
