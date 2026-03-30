"""Snow-Town inter-layer contracts.

Defines the data contracts that flow between layers:
- OutcomeRecord: Ultra Magnus -> Sky-Lynx
- ImprovementRecommendation: Sky-Lynx -> Academy
- PersonaUpgradePatch: Academy -> Ultra Magnus
- AgentUpgradePatch: ST Agent Registry -> Metroplex
- ResearchSignal: Research Agents -> Sky-Lynx
"""

from .agent_upgrade_patch import AgentUpgradePatch
from .improvement_recommendation import (
    EvidenceBasis,
    ImprovementRecommendation,
    RecommendationType,
    TargetScope,
)
from .outcome_record import OutcomeRecord, PipelineTrace, TerminalOutcome
from .persona_upgrade_patch import PersonaFieldPatch, PersonaUpgradePatch
from .research_signal import ResearchSignal, SignalRelevance, SignalSource
from .store import ContractStore

__all__ = [
    "AgentUpgradePatch",
    "OutcomeRecord",
    "PipelineTrace",
    "TerminalOutcome",
    "ImprovementRecommendation",
    "RecommendationType",
    "TargetScope",
    "EvidenceBasis",
    "PersonaUpgradePatch",
    "PersonaFieldPatch",
    "ResearchSignal",
    "SignalRelevance",
    "SignalSource",
    "ContractStore",
]
