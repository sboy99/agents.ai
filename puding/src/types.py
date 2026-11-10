from enum import Enum
from typing import TypedDict

from pydantic import BaseModel, Field


class Phase(str, Enum):
    IDEA = "idea"
    PLANNED = "planned"
    SPEC = "spec"
    TASKS = "tasks"


class ProductState(TypedDict, total=False):
    phase: Phase
    idea: str
    research: dict
    answers: dict[str, str]
    pending_questions: list[dict]
    scorecard: dict
    docs: dict
    notion_parent_id: str | None
    tickets: list[dict]


# ---- Structured LLM outputs ----
class OpenQuestion(BaseModel):
    id: str
    question: str
    why: str = ""


class Competitor(BaseModel):
    name: str
    positioning: str = ""
    strengths: str = ""
    weaknesses: str = ""


class ResearchDossier(BaseModel):
    summary: str
    competitors: list[Competitor] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    trends: list[str] = Field(default_factory=list)
    questions: list[OpenQuestion] = Field(default_factory=list)
    virality_factors: list[str] = Field(default_factory=list)


class RiskItem(BaseModel):
    risk: str
    probability: int = 3
    impact: int = 3
    mitigation: str = ""


class Scorecard(BaseModel):
    verdict: str
    risk_matrix: list[RiskItem] = Field(default_factory=list)
    competitor_overview: str = ""
    virality_score: float = 0
    adoption_score: float = 0
    rationale: str = ""


class Docs(BaseModel):
    hld: str
    lld: str
    mermaid_hld: str
    mermaid_lld: str
    stack: str = ""


class Ticket(BaseModel):
    title: str
    prd: str
    acceptance: list[str] = Field(default_factory=list)
    priority: str = "medium"
    area: str = "core"
    out_of_scope: str = ""


class TicketList(BaseModel):
    tickets: list[Ticket]
