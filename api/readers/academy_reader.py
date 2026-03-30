"""Read persona YAML files from the ST Agent Registry.

Walks ~/projects/st-agent-registry/personas/*/persona.yaml and
returns AgentSummary / AgentDetail objects. Read-only — never modifies YAML.
"""

from pathlib import Path

import yaml

from api.models.responses import AgentDetail, AgentSummary

DEFAULT_PERSONAS_DIR = Path.home() / "projects" / "st-agent-registry" / "personas"


class AcademyReader:
    """Reads persona YAML files from the Academy directory."""

    def __init__(self, personas_dir: Path | None = None):
        self.personas_dir = personas_dir or DEFAULT_PERSONAS_DIR

    def _load_yaml(self, persona_id: str) -> dict | None:
        path = self.personas_dir / persona_id / "persona.yaml"
        if not path.exists():
            return None
        with open(path) as f:
            return yaml.safe_load(f)

    def _persona_ids(self) -> list[str]:
        if not self.personas_dir.exists():
            return []
        return sorted(
            d.name
            for d in self.personas_dir.iterdir()
            if d.is_dir() and (d / "persona.yaml").exists()
        )

    def list_agents(self) -> list[AgentSummary]:
        agents = []
        for pid in self._persona_ids():
            data = self._load_yaml(pid)
            if data is None:
                continue
            identity = data.get("identity", {})
            metadata = data.get("metadata", {})
            frameworks = data.get("frameworks", {})
            case_studies = data.get("case_studies", {})
            agents.append(
                AgentSummary(
                    id=pid,
                    name=identity.get("name", pid),
                    role=identity.get("role", ""),
                    category=metadata.get("category", ""),
                    framework_count=len(frameworks),
                    case_study_count=len(case_studies) if case_studies else 0,
                )
            )
        return agents

    def get_agent(self, agent_id: str) -> AgentDetail | None:
        data = self._load_yaml(agent_id)
        if data is None:
            return None
        identity = data.get("identity", {})
        voice = data.get("voice", {})
        metadata = data.get("metadata", {})
        frameworks = data.get("frameworks", {})
        case_studies = data.get("case_studies", {})

        return AgentDetail(
            id=agent_id,
            name=identity.get("name", agent_id),
            role=identity.get("role", ""),
            category=metadata.get("category", ""),
            framework_count=len(frameworks),
            case_study_count=len(case_studies) if case_studies else 0,
            background=identity.get("background", ""),
            era=identity.get("era"),
            notable_works=identity.get("notable_works", []),
            voice_tone=voice.get("tone", []),
            voice_phrases=voice.get("phrases", []),
            voice_style=voice.get("style", []),
            frameworks=list(frameworks.keys()),
            case_studies=list(case_studies.keys()) if case_studies else [],
            metadata={
                "version": metadata.get("version", ""),
                "author": metadata.get("author", ""),
                "created": str(metadata.get("created", "")),
                "updated": str(metadata.get("updated", "")),
                "tags": metadata.get("tags", []),
            },
        )
