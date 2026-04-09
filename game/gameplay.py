from __future__ import annotations

from dataclasses import dataclass
@dataclass(frozen=True)
class StageDefinition:
    key: str
    title: str
    description: str


STAGE_DEFINITIONS = [
    StageDefinition("setup", "Setup", "Configure teams, leaders, ideas, and brackets."),
    StageDefinition("team-leads-ideas", "Ideas Submission", "Master selects one submitter per team."),
    StageDefinition("all-ideas", "Open idea submission", "All team members can submit ideas."),
    StageDefinition("bracket-sorting", "Bracket sorting", "Master organizes ideas into brackets."),
    StageDefinition("round-1", "Round 1", "Users vote and nominate points on matchups."),
    StageDefinition("prepare-round-2", "Prepare Round 2", "Sort brackets and prepare the next round."),
    StageDefinition("scoring", "Scoring", "Finalize scoring and outcomes."),
    StageDefinition("complete", "Complete", "Game complete."),
]
