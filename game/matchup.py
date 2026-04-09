from __future__ import annotations

from uuid import uuid4


class Matchup:
    def __init__(
        self,
        left_idea_id=None,
        right_idea_id=None,
        *,
        matchup_id=None,
        name="",
        description="",
        bracket_id=None,
        round_id=None,
        bracket_round=1,
        order=0,
        is_custom=False,
        left_label=None,
        right_label=None,
    ):
        self.id = matchup_id or uuid4().hex
        self.left_idea_id = left_idea_id
        self.right_idea_id = right_idea_id
        self.name = name
        self.description = description
        self.bracket_id = bracket_id
        self.round_id = round_id
        self.bracket_round = int(bracket_round or 1)
        self.order = int(order or 0)
        self.is_custom = bool(is_custom)
        self.left_label = left_label
        self.right_label = right_label

    @property
    def idea_ids(self):
        return [idea_id for idea_id in [self.left_idea_id, self.right_idea_id] if idea_id]

    def to_dict(self):
        return {
            "id": self.id,
            "left_idea_id": self.left_idea_id,
            "right_idea_id": self.right_idea_id,
            "idea_ids": self.idea_ids,
            "name": self.name,
            "description": self.description,
            "bracket_id": self.bracket_id,
            "round_id": self.round_id,
            "bracket_round": self.bracket_round,
            "order": self.order,
            "is_custom": self.is_custom,
            "left_label": self.left_label,
            "right_label": self.right_label,
        }

    @classmethod
    def from_dict(cls, data):
        left = data.get("left_idea_id")
        right = data.get("right_idea_id")
        if not left and not right:
            idea_ids = list(data.get("idea_ids", []))
            left = idea_ids[0] if len(idea_ids) > 0 else None
            right = idea_ids[1] if len(idea_ids) > 1 else None
        return cls(
            left,
            right,
            matchup_id=data.get("id"),
            name=data.get("name", ""),
            description=data.get("description", ""),
            bracket_id=data.get("bracket_id"),
            round_id=data.get("round_id"),
            bracket_round=data.get("bracket_round", 1),
            order=data.get("order", 0),
            is_custom=data.get("is_custom", False),
            left_label=data.get("left_label"),
            right_label=data.get("right_label"),
        )
