from enum import Enum
from uuid import uuid4

from .idea import Idea
from .matchup import Matchup


class BracketType(Enum):
    ROUND_ROBIN = "Round Robin"
    SINGLE_ELIMINATION = "Single Elimination"
    DOUBLE_ELIMINATION = "Double Elimination"
    SWISS = "Swiss"
    WINNER = "Winner"


class Bracket:
    bracket_type_name = BracketType.SWISS.value

    def __init__(
        self,
        name,
        bracket_id=None,
        bracket_type=None,
        description="",
        output_count=0,
        swiss_rounds=3,
        outputs=None,
        standings=None,
        matches=None,
        matchups=None,
        seed_order=None,
    ):
        self.id = bracket_id or uuid4().hex
        self.name = name
        self.ideas = []
        self.type = bracket_type
        self.description = description
        self.output_count = max(0, int(output_count or 0))
        self.swiss_rounds = max(1, int(swiss_rounds or 3))
        self.outputs = list(outputs or [])
        self.standings = dict(standings or {})
        self.matches = list(matches or [])
        self.matchups = [matchup if isinstance(matchup, Matchup) else Matchup.from_dict(matchup) for matchup in (matchups or [])]
        self.seed_order = list(seed_order or [])
        self.ensure_outputs()

    def ensure_outputs(self):
        desired = max(0, int(self.output_count or 0))
        current = []
        for item in self.outputs:
            if isinstance(item, dict):
                current.append(
                    {
                        "slot": int(item.get("slot", len(current) + 1)),
                        "idea_id": item.get("idea_id"),
                    }
                )
        while len(current) < desired:
            current.append({"slot": len(current) + 1, "idea_id": None})
        self.outputs = current[:desired]

    def set_output_count(self, output_count):
        self.output_count = max(0, int(output_count or 0))
        self.ensure_outputs()

    def output_label(self, slot):
        return f"{self.name} output {int(slot)}"

    def can_generate_pairings(self):
        return True

    def set_swiss_rounds(self, swiss_rounds):
        self.swiss_rounds = max(1, int(swiss_rounds or 1))

    def seeded_ids(self):
        valid = {idea.id for idea in self.ideas}
        ordered = [idea_id for idea_id in self.seed_order if idea_id in valid]
        for idea in self.ideas:
            if idea.id not in ordered:
                ordered.append(idea.id)
        return ordered

    def idea_label(self, idea_id):
        idea = next((idea for idea in self.ideas if idea.id == idea_id), None)
        return idea.title if idea else str(idea_id)

    def generate_matchups(self):
        return self.next_pairings()

    def add_idea(self, idea: Idea):
        if idea not in self.ideas:
            self.ideas.append(idea)
        idea.bracket_id = self.id
        self.ensure_standing(idea.id)
        if idea.id not in self.seed_order:
            self.seed_order.append(idea.id)

    def remove_idea(self, idea: Idea):
        if idea in self.ideas:
            self.ideas.remove(idea)
        if idea.bracket_id == self.id:
            idea.bracket_id = None
        if idea.id in self.seed_order:
            self.seed_order.remove(idea.id)

    def get_ideas(self):
        return self.ideas

    def ensure_standing(self, idea_id):
        if idea_id not in self.standings:
            self.standings[idea_id] = {
                "played": 0,
                "won": 0,
                "lost": 0,
                "tied": 0,
                "points": 0,
                "eliminations": 0,
                "score_for": 0,
                "score_against": 0,
            }
        return self.standings[idea_id]

    def record_match(self, match_result):
        """
        Persist a played match and update standings.

        Expected shape:
        {
            "matchup_id": str,
            "idea_ids": [id_a, id_b],
            "scores": {id_a: int, id_b: int},
            "winner_id": id or None,
            "tie": bool,
        }
        """
        idea_ids = list(match_result.get("idea_ids", []))
        if len(idea_ids) < 1:
            return

        scores = dict(match_result.get("scores", {}))
        winner_id = match_result.get("winner_id")
        is_tie = bool(match_result.get("tie", False))

        for idea_id in idea_ids:
            entry = self.ensure_standing(idea_id)
            entry["played"] += 1
            entry["score_for"] += int(scores.get(idea_id, 0) or 0)
            entry["score_against"] += sum(int(scores.get(other_id, 0) or 0) for other_id in idea_ids if other_id != idea_id)

        if len(idea_ids) == 2:
            left, right = idea_ids
            left_entry = self.ensure_standing(left)
            right_entry = self.ensure_standing(right)

            if is_tie:
                left_entry["tied"] += 1
                right_entry["tied"] += 1
                # round-robin and swiss style points
                left_entry["points"] += 1
                right_entry["points"] += 1
            else:
                loser_id = right if winner_id == left else left
                winner_entry = self.ensure_standing(winner_id)
                loser_entry = self.ensure_standing(loser_id)
                winner_entry["won"] += 1
                loser_entry["lost"] += 1
                # round-robin and swiss style points
                winner_entry["points"] += 3

                if self.type == BracketType.DOUBLE_ELIMINATION.value:
                    loser_entry["eliminations"] += 1
                elif self.type == BracketType.SINGLE_ELIMINATION.value:
                    loser_entry["eliminations"] = 1

        self.matches.append(match_result)

    def ranking(self):
        def sort_key(item):
            idea_id, data = item
            return (
                -int(data.get("points", 0)),
                -int(data.get("won", 0)),
                -int(data.get("score_for", 0) - data.get("score_against", 0)),
                int(data.get("eliminations", 0)),
                str(idea_id),
            )

        return sorted(self.standings.items(), key=sort_key)

    def _already_played(self, idea_a, idea_b):
        pair = {idea_a, idea_b}
        for match in self.matches:
            ids = set(match.get("idea_ids", []))
            if len(ids) == 2 and ids == pair:
                return True
        return False

    def _active_idea_ids(self):
        ids = [idea.id for idea in self.ideas]
        for idea_id in ids:
            self.ensure_standing(idea_id)

        if self.type == BracketType.SINGLE_ELIMINATION.value:
            return [idea_id for idea_id in ids if int(self.standings.get(idea_id, {}).get("eliminations", 0)) < 1]
        if self.type == BracketType.DOUBLE_ELIMINATION.value:
            return [idea_id for idea_id in ids if int(self.standings.get(idea_id, {}).get("eliminations", 0)) < 2]
        return ids

    def next_pairings(self):
        """Return the next set of pairings for this bracket as Matchup objects."""
        active_ids = self._active_idea_ids()
        if len(active_ids) <= 1:
            return []

        # Establish base ordering: seed order first, then ranking fallback.
        seed_rank = {idea_id: idx for idx, idea_id in enumerate(self.seed_order)}

        def seed_key(idea_id):
            row = self.standings.get(idea_id, {})
            return (
                seed_rank.get(idea_id, 9999),
                -int(row.get("points", 0)),
                -int(row.get("won", 0)),
                idea_id,
            )

        ordered = sorted(active_ids, key=seed_key)

        if self.type in {BracketType.SINGLE_ELIMINATION.value, BracketType.DOUBLE_ELIMINATION.value}:
            # Standard seeding: top vs bottom.
            pairings = []
            pool = list(ordered)
            while len(pool) > 1:
                left = pool.pop(0)
                right = pool.pop(-1)
                pairings.append(Matchup(left, right, bracket_id=self.id))
            if pool:
                pairings.append(Matchup(pool[0], None, bracket_id=self.id))
            return pairings

        if self.type == BracketType.ROUND_ROBIN.value:
            # Next unplayed pairs only.
            pairings = []
            used = set()
            for i, idea_a in enumerate(ordered):
                if idea_a in used:
                    continue
                for idea_b in ordered[i + 1 :]:
                    if idea_b in used:
                        continue
                    if not self._already_played(idea_a, idea_b):
                        pairings.append(Matchup(idea_a, idea_b, bracket_id=self.id))
                        used.add(idea_a)
                        used.add(idea_b)
                        break
            leftovers = [idea_id for idea_id in ordered if idea_id not in used]
            for idea_id in leftovers:
                pairings.append(Matchup(idea_id, None, bracket_id=self.id))
            return pairings

        if self.type == BracketType.SWISS.value:
            # Pair by similar points, avoid rematches when possible.
            swiss_sorted = sorted(
                ordered,
                key=lambda idea_id: (
                    -int(self.standings.get(idea_id, {}).get("points", 0)),
                    -int(self.standings.get(idea_id, {}).get("won", 0)),
                    idea_id,
                ),
            )
            pairings = []
            pool = list(swiss_sorted)
            while len(pool) > 1:
                idea_a = pool.pop(0)
                match_idx = None
                for idx, candidate in enumerate(pool):
                    if not self._already_played(idea_a, candidate):
                        match_idx = idx
                        break
                if match_idx is None:
                    match_idx = 0
                idea_b = pool.pop(match_idx)
                pairings.append(Matchup(idea_a, idea_b, bracket_id=self.id))
            if pool:
                pairings.append(Matchup(pool[0], None, bracket_id=self.id))
            return pairings

        return []

    def stage_label(self):
        return self.name

    def preview_lines(self, idea_lookup):
        seed_labels = [idea_lookup(idea_id) for idea_id in self.seed_order if idea_lookup(idea_id)]
        if not seed_labels:
            seed_labels = [idea.title for idea in self.ideas]
        lines = [f"Seed {idx + 1}: {title}" for idx, title in enumerate(seed_labels)]
        return lines or ["No ideas yet."]

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "output_count": self.output_count,
            "swiss_rounds": self.swiss_rounds,
            "outputs": list(self.outputs),
            "idea_ids": [idea.id for idea in self.ideas],
            "standings": dict(self.standings),
            "matches": list(self.matches),
            "matchups": [matchup.to_dict() for matchup in self.matchups],
            "seed_order": list(self.seed_order),
        }

    @classmethod
    def from_dict(cls, data):
        bracket_type = data.get("type") or BracketType.SWISS.value
        bracket_cls = BRACKET_CLASS_BY_TYPE.get(bracket_type, Bracket)
        bracket = cls(
            data.get("name", ""),
            bracket_id=data.get("id"),
            bracket_type=bracket_type,
            description=data.get("description", ""),
            output_count=data.get("output_count", 0),
            swiss_rounds=data.get("swiss_rounds", 3),
            outputs=data.get("outputs", []),
            standings=data.get("standings", {}),
            matches=data.get("matches", []),
            matchups=data.get("matchups", []),
            seed_order=data.get("seed_order", []),
        )
        if bracket_cls is not cls:
            bracket = bracket_cls.from_dict(data)
        bracket.idea_ids = list(data.get("idea_ids", []))
        return bracket


class SwissBracket(Bracket):
    bracket_type_name = BracketType.SWISS.value

    def generate_matchups(self):
        pairings = self.next_pairings()
        out = []
        for idx, pairing in enumerate(pairings, start=1):
            if isinstance(pairing, Matchup):
                pairing.bracket_round = 1
                pairing.order = idx
                pairing.name = pairing.name or f"{self.name} R1 M{idx}"
                out.append(pairing)
            else:
                ids = pairing.get("idea_ids", [])
                left = ids[0] if len(ids) > 0 else None
                right = ids[1] if len(ids) > 1 else None
                out.append(Matchup(left, right, bracket_id=self.id, bracket_round=1, order=idx, name=f"{self.name} R1 M{idx}"))
        return out


class RoundRobinBracket(Bracket):
    bracket_type_name = BracketType.ROUND_ROBIN.value

    def generate_matchups(self):
        ids = self.seeded_ids()
        if len(ids) <= 1:
            return []

        players = list(ids)
        if len(players) % 2 == 1:
            players.append(None)

        rounds = len(players) - 1
        half = len(players) // 2
        rows = []
        rotation = list(players)
        order = 1
        for round_no in range(1, rounds + 1):
            left = rotation[:half]
            right = list(reversed(rotation[half:]))
            for a, b in zip(left, right):
                if a is None or b is None:
                    continue
                rows.append(
                    Matchup(
                        a,
                        b,
                        bracket_id=self.id,
                        bracket_round=round_no,
                        order=order,
                        name=f"{self.name}, Round {round_no}: {self.idea_label(a)} vs {self.idea_label(b)}",
                    )
                )
                order += 1
            # circle rotation
            fixed = rotation[0]
            rest = rotation[1:]
            rest = [rest[-1], *rest[:-1]]
            rotation = [fixed, *rest]
        return rows


class SingleEliminationBracket(Bracket):
    bracket_type_name = BracketType.SINGLE_ELIMINATION.value

    def generate_matchups(self):
        seeds = self.seeded_ids()
        if len(seeds) <= 1:
            return []

        entries = [{"id": idea_id, "label": self.idea_label(idea_id)} for idea_id in seeds]
        matchups = []
        round_no = 1
        order = 1
        while len(entries) > 1:
            pairings = []
            pool = list(entries)
            while len(pool) > 1:
                pairings.append((pool.pop(0), pool.pop(-1)))
            if pool:
                pairings.append((pool[0], None))

            next_entries = []
            for left, right in pairings:
                left_id = left.get("id") if left else None
                right_id = right.get("id") if right else None
                left_label = left.get("label") if left else None
                right_label = right.get("label") if right else None
                matchup = Matchup(
                    left_id,
                    right_id,
                    bracket_id=self.id,
                    bracket_round=round_no,
                    order=order,
                    name=f"{self.name}, Round {round_no}: {left_label or 'TBD'} vs {right_label or 'TBD'}",
                    left_label=left_label,
                    right_label=right_label,
                )
                matchups.append(matchup)
                order += 1

                if left and not right:
                    next_entries.append({"id": left_id, "label": left_label})
                elif right and not left:
                    next_entries.append({"id": right_id, "label": right_label})
                else:
                    next_entries.append({"id": None, "label": f"Winner of {left_label or 'TBD'} vs {right_label or 'TBD'}"})

            entries = next_entries
            round_no += 1
        return matchups


class DoubleEliminationBracket(Bracket):
    bracket_type_name = BracketType.DOUBLE_ELIMINATION.value

    def generate_matchups(self):
        # Winners-bracket generation (tree structure). Full lower-bracket progression
        # is resolved as results are recorded.
        return SingleEliminationBracket.generate_matchups(self)


class WinnerBracket(Bracket):
    bracket_type_name = BracketType.WINNER.value

    def can_generate_pairings(self):
        return False

    def next_pairings(self):
        return []

    def generate_matchups(self):
        return []


BRACKET_CLASS_BY_TYPE = {
    BracketType.SWISS.value: SwissBracket,
    BracketType.ROUND_ROBIN.value: RoundRobinBracket,
    BracketType.SINGLE_ELIMINATION.value: SingleEliminationBracket,
    BracketType.DOUBLE_ELIMINATION.value: DoubleEliminationBracket,
    BracketType.WINNER.value: WinnerBracket,
}

