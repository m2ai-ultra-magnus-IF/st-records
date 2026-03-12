"""ImprovementRecommendation contract: Sky-Lynx -> Academy.

Replaces Sky-Lynx's free-form markdown with typed proposals.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class RecommendationType(str, Enum):
    """Types of improvement recommendations."""
    VOICE_ADJUSTMENT = "voice_adjustment"
    FRAMEWORK_ADDITION = "framework_addition"
    FRAMEWORK_REFINEMENT = "framework_refinement"
    VALIDATION_MARKER_CHANGE = "validation_marker_change"
    CASE_STUDY_ADDITION = "case_study_addition"
    CONSTRAINT_ADDITION = "constraint_addition"
    CONSTRAINT_REMOVAL = "constraint_removal"
    CLAUDE_MD_UPDATE = "claude_md_update"
    PIPELINE_CHANGE = "pipeline_change"
    TIER_PROMOTION = "tier_promotion"
    TIER_DEMOTION = "tier_demotion"
    OTHER = "other"


class TargetScope(str, Enum):
    """Scope of the recommendation."""
    SPECIFIC_PERSONA = "specific_persona"
    ALL_PERSONAS = "all_personas"
    ALL_IN_DEPARTMENT = "all_in_department"


class EvidenceBasis(BaseModel):
    """Evidence supporting a recommendation."""
    outcome_record_ids: list[int] = Field(default_factory=list)
    pattern_frequency: int = Field(ge=1, default=1)
    signal_strength: float = Field(ge=0.0, le=1.0, default=0.5)
    description: str = ""


class ImprovementRecommendation(BaseModel):
    """Typed recommendation from Sky-Lynx to Academy.

    Precondition: pattern_frequency >= 1.
    Postcondition: parseable by Academy without knowledge of SL internals.
    """
    contract_version: str = "1.0.0"
    recommendation_id: str
    session_id: str = ""
    recommendation_type: RecommendationType
    target_system: str = "persona"  # persona | claude_md | pipeline
    title: str
    description: str
    suggested_change: str
    scope: TargetScope = TargetScope.ALL_PERSONAS
    target_persona_ids: list[str] = Field(default_factory=list)
    target_department: str | None = None
    priority: str = "medium"  # high | medium | low
    impact: str = ""
    reversibility: str = "high"  # high | medium | low
    evidence: EvidenceBasis = Field(default_factory=EvidenceBasis)
    status: str = "pending"  # pending | dispatched | applied | rejected
    emitted_at: datetime = Field(default_factory=datetime.now)

    @model_validator(mode="after")
    def validate_scope_targets(self) -> "ImprovementRecommendation":
        """Validate scope-dependent fields.

        - SPECIFIC_PERSONA requires target_persona_ids
        - ALL_IN_DEPARTMENT requires target_department
        """
        if self.scope == TargetScope.SPECIFIC_PERSONA and not self.target_persona_ids:
            raise ValueError(
                "target_persona_ids must be non-empty when scope is specific_persona"
            )
        if self.scope == TargetScope.ALL_IN_DEPARTMENT and not self.target_department:
            raise ValueError(
                "target_department must be set when scope is all_in_department"
            )
        return self
