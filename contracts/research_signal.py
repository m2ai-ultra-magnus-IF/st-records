"""ResearchSignal contract: Research Agents -> Sky-Lynx.

Emitted when a research agent discovers a signal (paper, tool, trend)
relevant to the Snow-Town ecosystem.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SignalSource(str, Enum):
    """Source agent that produced the signal."""
    ARXIV_HF = "arxiv_hf"
    TOOL_MONITOR = "tool_monitor"
    DOMAIN_WATCH = "domain_watch"
    IDEA_MACHINE = "idea_machine"
    YOUTUBE_SCANNER = "youtube_scanner"
    RSS_SCANNER = "rss_scanner"
    MANUAL = "manual"
    TREND_ANALYZER = "trend_analyzer"
    PERPLEXITY = "perplexity"
    CHATGPT = "chatgpt"
    GEMINI_RESEARCH = "gemini_research"


class SignalRelevance(str, Enum):
    """Relevance assessment level."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ResearchSignal(BaseModel):
    """Signal emitted by a research agent.

    Precondition: relevance assessment completed by Claude API.
    Postcondition: record is append-only, written to JSONL + SQLite.
    Invariant: signal_id is unique; contract_version always present.
    """
    contract_version: str = "1.0.0"
    signal_id: str
    source: SignalSource
    title: str
    summary: str
    url: str | None = None
    relevance: SignalRelevance
    relevance_rationale: str = ""
    tags: list[str] = Field(default_factory=list)
    domain: str | None = None
    raw_data: dict | None = None
    consumed_by: str | None = None
    emitted_at: datetime = Field(default_factory=datetime.now)
