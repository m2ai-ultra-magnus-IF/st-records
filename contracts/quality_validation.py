"""QualityValidation contract: Ultra Magnus (Tyrest) -> Sky-Lynx.

Emitted after each Tyrest QA validation. Enables Sky-Lynx to track
Tyrest accuracy trends in weekly analysis.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class QAVerdictContract(str, Enum):
    """QA validation verdict (mirrors idea-factory QAVerdict)."""

    APPROVE = "approve"
    REQUEST_REVIEW = "request_review"
    REJECT = "reject"


class QualityValidation(BaseModel):
    """Record emitted after each Tyrest QA validation.

    Precondition: build must exist for the idea.
    Postcondition: record is append-only, written to JSONL + SQLite.
    Invariant: contract_version always present; scores in [0, 1].
    """

    contract_version: str = "1.0.0"
    idea_id: str
    verdict: QAVerdictContract
    overall_score: float = Field(..., ge=0.0, le=1.0)
    spec_alignment_score: float | None = Field(default=None, ge=0.0, le=1.0)
    test_quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    artifact_completeness_score: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    confidence_override_applied: bool = False
    findings_count: int = 0
    model_used: str = "gpt-4.1"
    build_outcome: str | None = None
    routed_to: str = ""
    emitted_at: datetime = Field(default_factory=datetime.now)
