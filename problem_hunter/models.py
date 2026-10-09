"""Shared serializable domain objects; counts represent observations, not demand."""
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass
class Source:
    url: str
    title: str
    content: str
    source: str = "web"
    author: Optional[str] = None
    published_at: Optional[str] = None
    content_kind: str = "full_text"
    metadata: dict = field(default_factory=dict)
    id: str = ""


@dataclass
class Problem:
    source_id: str
    statement: str
    category: str
    judgments: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)
    id: str = ""


@dataclass
class Opportunity:
    id: str
    title: str
    description: str
    category: str
    problem_ids: list = field(default_factory=list)
    source_ids: list = field(default_factory=list)
    independent_sources: int = 0
    independent_complainants: int = 0
    score: float = 0.0
    evidence_strength: str = "weak"
    score_breakdown: dict = field(default_factory=dict)
    solutions: list = field(default_factory=list)
    potential_fixes: list = field(default_factory=list)
    unknowns: list = field(default_factory=list)
    next_step: str = "Interview independent affected users and verify costs."
    research_status: str = "pending"
    bookmarked: bool = False


def serialize(value: Any) -> dict:
    return asdict(value)
