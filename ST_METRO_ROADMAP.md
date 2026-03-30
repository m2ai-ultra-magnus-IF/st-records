# ST Metro Level 5 Roadmap

**Last updated**: 2026-02-23 (reviewed post-DR)
**Owner**: Matthew Snow
**Vision**: Fully autonomous software production — the human doesn't write the code, the human doesn't review the code.

---

## Current State

```
Research Agents (ArXiv API, GitHub API, HN Algolia + Claude relevance assessment)
    |
    v
ST Records ContractStore (ResearchSignals — JSONL + SQLite)
    |
    v
idea_surfacer (Claude synthesis — signals → project ideas)
    |
    v
Ultra-Magnus / IdeaForge (idea pipeline, Christensen scoring)
    |
    v
YCE Harness (autonomous build engine, multi-agent, parallel worktrees)
    |
    v
Sky-Lynx (weekly analysis, CLAUDE.md recommendations)
    |
    v
ST Records (persona metrics, contract store, patch management)
    |
    v
Agent Persona Academy (persona YAMLs)
    |
    ... cycle repeats (manually)

ClaudeClaw "Data" (Telegram Chief of Staff, multi-LLM routing)
Clawdbot "Chad" (GPT-5.2 multi-agent system)
Metroplex (L5 autonomy coordinator — built, awaiting pipeline data)
```

**The gap**: Each piece is built and tested, but the research agents have never run (cron paths still reference the dead EC2 instance). The pipeline is wired but dormant — no signals flowing means nothing downstream has data to act on. Metroplex is built and deployed but idle.

---

## Component Status

| Component | Location | Status | Purpose |
|-----------|----------|--------|---------|
| IdeaForge | `projects/ideaforge/` | Built | Market signal ingestion, shared SQLite schema |
| Research Agents | `projects/research-agents/` | Built (dormant) | 4 agents: arxiv_scanner, tool_monitor, domain_watcher, idea_surfacer. Uses ArXiv/GitHub/HN APIs + Claude relevance. Cron not installed post-DR. |
| Ultra-Magnus | `projects/ultra-magnus/` | Built | Idea capture, Gemini enrichment, Christensen evaluation, HIL review, scaffold, build, deploy |
| YCE Harness | `projects/yce-harness/` | Built | Autonomous AI engineer — Orchestrator (Haiku) + specialist agents (Sonnet), parallel via worktrees |
| Sky-Lynx | remote: `m2ai-portfolio/sky-lynx` | Built | Weekly cron analysis, reads usage + IdeaForge + ST Records, recommends CLAUDE.md updates |
| ST Records | `projects/st-records/` | Built | Persona metrics DB, contract store, patch management |
| ST Agent Registry | remote: `m2ai-ultra-magnus-IF/st-agent-registry` | Built | Persona YAML definitions, department system, agent learning copies |
| ClaudeClaw "Data" | `projects/claudeclaw/` | Built (Phase 7 in progress) | Telegram bot, Claude Code backend, multi-LLM routing, Arcade MCP |
| Clawdbot "Chad" | External (GPT-5.2) | Running | Independent multi-agent system at `@m2ai_chad_bot` |
| Metroplex | `projects/metroplex/` | Built (idle) | L5 autonomy coordinator — 3 gates (triage/build/patch), circuit breaker, systemd service. Awaiting pipeline data. |
| AlienPC | `ssh matth@10.0.0.35` | Online | RTX 5080, Unity, ComfyUI — GPU workstation for games, image/video gen, VR |

---

## The L5 Architecture

### Three Input Streams

**1. Signal-driven (market pull)**
```
Research Agents (daily cron)
    -> IdeaForge (normalize signals)
    -> Ultra-Magnus (evaluate + score via Christensen framework)
    -> Metroplex priority queue
```
The market tells the system what to build. No human required to identify opportunities.

**2. Self-improvement driven (internal push)**
```
Sky-Lynx (weekly analysis of Claude Code usage, IdeaForge DB, ST Records metrics)
    -> Recommended patches (CLAUDE.md updates, persona improvements)
    -> Metroplex priority queue
```
The system observes its own performance and generates improvement tasks.

**3. Backlog-driven (strategic direction)**
```
Matthew (via Data/Telegram or direct Linear)
    -> Standing backlog in Linear
    -> Metroplex priority queue
```
Human sets strategy, priorities, and constraints. Does not write or review code.

### Unified Flow

```
 Signal Agents ──┐
 Sky-Lynx ───────┼──> Metroplex Priority Queue
 Linear Backlog ─┘           |
                             |  (ranked by: market score, self-improvement ROI, human priority)
                             v
                    ┌─────────────────┐
                    │    Metroplex    │
                    │  (Coordinator)  │
                    └────────┬────────┘
                             |
              ┌──────────────┼──────────────┐
              v              v              v
        YCE Harness    Data (Claude)   Chad (GPT-5.2)
        (build engine)  (ops/research)  (second opinion)
              |              |              |
              v              v              v
        Feature branches   Linear updates  Linear updates
              |              |              |
              v              v              v
        ┌─────────────────────────────────────┐
        │         GitHub / Linear / Slack     │
        │        (shared state via Arcade)    │
        └──────────────────┬──────────────────┘
                           |
                           v
                    ST Records (metrics)
                           |
                           v
                    Sky-Lynx (observes)
                           |
                           └──> new tasks ──> Metroplex queue
                                              (cycle repeats)
```

### Human Role in L5

| Old (L3-L4) | New (L5) |
|---|---|
| Write code | Set strategy and constraints |
| Review PRs | Define evaluation criteria (Christensen scoring, QA gates) |
| Assign tasks | Curate signal sources (which markets, which research agents) |
| Schedule work | Set guardrails (repo access, branch policies, budget limits) |
| Debug failures | Review outcomes (optional — can be automated) |
| Coordinate agents | Handled by Metroplex |

---

## Roadmap

### Phase 7: Activate the Pipeline — IN PROGRESS

**Owner**: Research Agents + ST Records
**Goal**: Get signals flowing through the full pipeline so Metroplex has data to act on

| Step | Description | Status |
|------|-------------|--------|
| 7a | Fix research-agents cron paths (`/home/ubuntu/` → `/home/apexaipc/`) | Done |
| 7b | Verify `run-agents.sh` works in local environment — venv recreated, 28 tests passing | Done |
| 7c | Dry-run all 4 agents — arxiv, tool-monitor, domain-watch all fetch data | Done |
| 7d | Live run — 63 signals (18 arxiv, 20 tool, 25 domain) written to ST Records | Done |
| 7e | Verify idea_surfacer writes to Ultra-Magnus — 3 ideas synthesized into caught_ideas.db | Done |
| 7f | Install cron on local machine | Done |
| 7g | Verify Metroplex triage picks up scored ideas (requires UM scoring first) | Not started |

**Exit criteria**: Research agents run on cron, signals flow into ST Records, idea_surfacer produces ideas, Metroplex triage has data to approve/reject/defer.

---

### Phase 8: Bot-to-Bot Coordination via Linear — ON HOLD

**Owner**: ClaudeClaw project
**Goal**: Data and Chad share a Linear work queue via Arcade MCP
**Status**: On hold pending decision on Clawdbot's future role in ecosystem.

| Step | Description | Status |
|------|-------------|--------|
| 8a | Arcade MCP config for ClaudeClaw | Done |
| 8b | Shared Linear project ("Bot Ops", M2A-122 META issue), label conventions | Done |
| 8c | Clawdbot synchronous endpoint (request/response) | On hold |
| 8d | Coordination patterns (handoff, second opinion, pipeline) | On hold |
| 8e | Loop prevention and safety (max turns, cooldown, dead letter) | On hold |

**Exit criteria**: Data can create a Linear issue, Chad picks it up, result flows back to Data, Matthew is notified via Telegram.

---

### Phase 9: Metroplex Priority Queue

**Owner**: Metroplex project
**Goal**: Autonomous task coordinator that pulls from multiple input streams and dispatches to agents

| Step | Description | Status |
|------|-------------|--------|
| 9a | Priority queue — ingest from IdeaForge, Sky-Lynx, Linear backlog | TBD |
| 9b | Task ranking — market score, self-improvement ROI, human priority weight | TBD |
| 9c | Agent dispatch — route tasks to YCE Harness, Data, or Chad | TBD |
| 9d | Progress tracking — monitor agent output, update Linear, report to Data | TBD |
| 9e | Overnight mode — continuous operation with configurable schedule windows | TBD |
| 9f | Agent-to-agent handoff — enable Claude Code sessions to dispatch tasks to Data (ClaudeClaw) directly via n8n workflow or Telegram API, eliminating human relay for task handoffs. Currently Perceptor context is async and requires manual load. | TBD |

**Exit criteria**: Metroplex pulls a scored idea from Ultra-Magnus, dispatches it to YCE Harness, code lands on a feature branch, status reported to Telegram. No human touched it.

**Dependencies**: Phase 7 (pipeline active with real data)

---

### Phase 10: Self-Improvement Loop Closure

**Goal**: Sky-Lynx output feeds directly back into Metroplex, closing the autonomous improvement cycle

| Step | Description | Status |
|------|-------------|--------|
| 10a | Sky-Lynx writes improvement tasks to Linear (not just draft PRs) | Not started |
| 10b | ST Records metrics auto-generate persona patch tasks | Not started |
| 10c | Metroplex ingests improvement tasks alongside market tasks | Not started |
| 10d | Validation gate — self-improvement changes must pass before merging | Not started |

**Exit criteria**: Sky-Lynx identifies a recurring failure pattern, generates a fix task, Metroplex dispatches it, agent implements and validates it, CLAUDE.md or persona YAML is updated. No human touched it.

---

### Phase 11: Research Agent Redesign (Ng/Jones Pattern)

**Goal**: Upgrade research agents from keyword scraping to strategic intelligence, leveraging Perplexity, ChatGPT, and Gemini subscriptions for multi-LLM signal diversity

| Step | Description | Status |
|------|-------------|--------|
| 11a | Design research patterns inspired by Andrew Ng ("The Batch") and Nate B Jones (AI strategy) | Not started |
| 11b | Perplexity agent — citation-backed market research, real-time web search | Not started |
| 11c | ChatGPT agent — consumer-lens reframing, willingness-to-pay signals (spec exists) | Not started |
| 11d | Gemini agent — trend detection, Google ecosystem intelligence | Not started |
| 11e | Thematic synthesis — weekly digest across all sources (not just per-signal) | Not started |
| 11f | Quality feedback — Sky-Lynx correlates signal source with idea outcome quality | Not started |

**Exit criteria**: Multi-LLM research fleet produces strategically framed signals. Sky-Lynx data shows which LLM sources produce highest-scoring ideas. System self-tunes research queries based on outcomes.

**Principle**: Don't let perfect research block the loop. Let the loop help you build perfect research. The existing agents (ArXiv/GitHub/HN) run first; this redesign is informed by real pipeline data on what signal quality looks like.

**Dependencies**: Phase 7 (pipeline active), Phase 10 (Sky-Lynx feedback on signal quality)

---

### Phase 12: GPU Workstation Integration (AlienPC)

**Goal**: Metroplex can dispatch GPU-dependent tasks to AlienPC via SSH

| Step | Description | Status |
|------|-------------|--------|
| 12a | SSH bridge abstraction (Linux workstation -> AlienPC) | Verified (manual) |
| 12b | ComfyUI API integration — image/video generation tasks | Not started |
| 12c | Unity CLI builds — headless build and test for game projects | Not started |
| 12d | Local model inference — run models on RTX 5080 when needed | Not started |

**Exit criteria**: Metroplex can dispatch "generate marketing images for project X" to AlienPC, ComfyUI produces assets, results stored and linked to the project.

**AlienPC inventory**:
- RTX 5080 (16 GB VRAM), 64 GB RAM, Windows 11 Pro
- Unity Hub: 2022.3.0f1, 2022.3.62f3, 6000.1.0f1
- ComfyUI: checkpoints, LoRAs, AnimateDiff, CogVideo, LivePortrait, etc.
- Projects: robotech-turn-based-game, mcp-dsp, vigilai-dcs-wingman, Project Valkyrie

---

### Phase 13: Full Dark Factory

**Goal**: End-to-end autonomous operation — signal to shipped product with zero human intervention

| Step | Description | Status |
|------|-------------|--------|
| 13a | Auto-merge policy — feature branches merge after QA gate passes | Not started |
| 13b | Auto-deploy — CI/CD triggers on merge (Vercel, Railway) | Not started |
| 13c | Human review elimination — replace with automated code review agent scoring | Not started |
| 13d | Anomaly detection — alert Matthew only on failures, not on successes | Not started |
| 13e | Budget controls — rate limiting, cost caps, automatic shutdown thresholds | Not started |

**Exit criteria**: A market signal enters IdeaForge on Monday morning. By Tuesday, a working MVP is deployed to production. Matthew's only notification is "New product shipped: [name], [url]." He never saw the code.

---

## Operational: API Billing Consolidation

Research agents currently use the Anthropic API (`ANTHROPIC_API_KEY`) for Claude relevance assessment — this is pay-per-token billing, separate from the Max plan. Investigate whether programmatic Claude usage can route through Max to avoid double-paying. This applies to:
- Research agents (relevance assessment via `anthropic.Anthropic`)
- Idea surfacer (synthesis via `anthropic.Anthropic`)
- Any future agent that calls Claude programmatically

**Action**: Check Max plan TOS for programmatic/API usage. If allowed, migrate. If not, evaluate whether Haiku (cheapest API tier) is sufficient for relevance classification.

---

## Guardrails (Non-Negotiable)

These apply at every phase:

1. **Branch protection** — Agents commit to feature branches, never main/develop directly
2. **Budget caps** — API spend limits per agent per day, auto-pause on breach
3. **Repo scope** — Each agent can only touch repos explicitly granted to it
4. **Kill switch** — Matthew can halt all autonomous operations via single Telegram command to Data
5. **Audit trail** — Every agent action logged (Linear comments, git commits, Slack messages)
6. **No secret exposure** — Agents never surface API keys, tokens, or credentials
7. **Escalation path** — If an agent is stuck for >N minutes, notify Matthew, don't loop

---

## Quick Reference

```
# ClaudeClaw (Data)
cd ~/projects/claudeclaw && npm run dev

# YCE Harness
cd ~/projects/yce-harness && source venv/bin/activate && python autonomous_agent_demo.py

# Ultra-Magnus
cd ~/projects/ultra-magnus/idea-factory && source .venv/bin/activate && uvicorn src.main:app --reload

# AlienPC
ssh -i ~/.ssh/gaming_pc_key matth@10.0.0.35

# Metroplex
cd ~/projects/metroplex && source venv/bin/activate
python metroplex.py status            # Check gate status
python metroplex.py run-all --dry-run  # Dry-run full cycle
python metroplex.py run-all --cycles 1 # Live single cycle

# Research Agents
cd ~/projects/research-agents && source .venv/bin/activate
research-agents status                 # Signal counts + config
research-agents run arxiv --dry-run    # Dry-run single agent
research-agents run-all --dry-run      # Dry-run all agents
```
