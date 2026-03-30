"""AgentUpgradePatch contract: ST Agent Registry -> Metroplex.

Section-level diffs for true agent CLAUDE.md and agent.yaml files.
Unlike PersonaUpgradePatch (JSON Pointer on YAML), agent patches
target markdown sections in CLAUDE.md or top-level keys in agent.yaml.
"""

from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class AgentUpgradePatch(BaseModel):
    """Patch describing changes to a true agent's config.

    Precondition: agent_id references a registered agent in st-agent-registry/agents/.
    Postcondition: applying patch yields a valid CLAUDE.md or agent.yaml.
    """

    contract_version: str = "1.0.0"
    patch_id: str
    agent_id: str
    target: str  # "claude_md" | "agent_yaml"
    section: str  # CLAUDE.md section header or agent.yaml top-level key
    operation: str  # "add" | "replace" | "remove"
    value: str | None = None
    rationale: str
    source_recommendation_ids: list[str] = Field(default_factory=list)
    status: str = "proposed"  # proposed | approved | applied | rejected
    emitted_at: datetime = Field(default_factory=datetime.now)

    @model_validator(mode="after")
    def validate_value_for_operation(self) -> "AgentUpgradePatch":
        """Add/replace operations require a value; remove does not."""
        if self.operation in ("add", "replace") and self.value is None:
            raise ValueError(f"{self.operation} operation requires a value")
        return self
