# Snow-Town Blueprint

## Phase Tracking

### Phase 0: Cleanup Dead Code
- [x] Delete `idea-factory/` directory
- [x] Delete `idea-factory-dashboard/` directory
- [x] Delete `processor.py`
- [x] Verify UM MCP server still starts

### Phase 1: Snow-Town Umbrella Repo + Shared Contracts
- [x] Create directory structure
- [x] Define OutcomeRecord contract
- [x] Define ImprovementRecommendation contract
- [x] Define PersonaUpgradePatch contract
- [x] Implement ContractStore (JSONL + SQLite)
- [x] Generate JSON schemas
- [x] Write contract tests (33 passing)
- [x] Create project files (README, CLAUDE.md, pyproject.toml)

### Phase 2: Outcome Recording in Ultra Magnus
- [x] Add `_emit_outcome_record()` to repository.py
- [x] Hook into `update_stage()` for terminal states
- [x] Hook into `set_github_url()` for published state
- [x] Add `um_record_outcome` tool to server.py
- [x] Add `record_outcome_manual()` for retroactive recording

### Phase 3: Structured Recommendations in Sky-Lynx
- [x] Create `outcome_reader.py` with digest builder
- [x] Extend `claude_client.py` with outcome data section
- [x] Add target_system, target_persona, recommendation_type to Recommendation model
- [x] Update parse_recommendations() to extract new fields
- [x] Add JSON sidecar writer to `report_writer.py`
- [x] Write ImprovementRecommendations to st-records JSONL store
- [x] Wire outcome reader in `analyzer.py`
- [x] All 28 existing tests still passing

### Phase 4: Persona Upgrade Engine
- [x] Create `persona_upgrader.py`
- [x] Implement Claude API patch generation with structured prompt
- [x] Add schema validation via Academy CLI
- [x] Add --dry-run, --auto-apply, --persona flags
- [x] JSON Pointer patch application logic

### Phase 5: Loop Orchestration
- [x] Create `run_loop.sh` (orchestrates SL -> upgrader -> status)
- [x] Create `loop_status.py` (reports all JSONL counts + health)
- [x] Create cron configuration
- [x] Dry-run test passes end-to-end

### Phase 6: Full Rename (Deferred)
- [ ] Present rename map for approval
- [ ] Execute renames

### Phase 7: Visualization

#### Phase 7a: Data API (FastAPI)
- [x] Create `api/models/responses.py` — Pydantic response models
- [x] Create `api/readers/academy_reader.py` — Read persona YAML files
- [x] Create `api/readers/um_reader.py` — Read UM SQLite database
- [x] Create `api/deps.py` — Shared dependencies with configurable paths
- [x] Create `api/routers/ecosystem.py` — Ecosystem snapshot endpoint
- [x] Create `api/routers/nodes.py` — Node detail endpoint
- [x] Create `api/routers/agents.py` — Agents endpoints
- [x] Create `api/routers/pipeline.py` — Pipeline endpoints
- [x] Create `api/routers/activity.py` — Activity feed endpoint (query_* with status overlay)
- [x] Create `api/main.py` — FastAPI app with CORS, lifespan, health check
- [x] Create test suite (19 tests, all passing)
- [x] Update `pyproject.toml` with API dependencies
- [x] Smoke-test all endpoints with real data (8 personas, 8 ideas, 1 patch)

#### Phase 7b: Dashboard Scaffold (Next.js + R3F)
- [x] Initialize Next.js 14 project with App Router
- [x] Configure Tailwind CSS with dark theme
- [x] Set up React Three Fiber + drei + xr dependencies
- [x] Create root layout with sidebar navigation
- [x] Create pages: Ecosystem (/), Agents (/agents), Pipeline (/pipeline)
- [x] Create dynamic routes: Node detail, Agent detail
- [x] Create API client + SWR hooks
- [x] Create TypeScript types matching API responses
- [x] Build passes, all routes return 200
- [x] Rewrite home page from 3D-only to proper dashboard (HealthBanner, NodeStatusCards, ActivityFeed)
- [x] Move 3D ecosystem view to dedicated /ecosystem route
- [x] Add pipeline detail page (/pipeline/[ideaId])
- [x] Add responsive sidebar with context provider
- [x] Add error states, filter controls, and component improvements

#### Phase 7c: 3D Ecosystem View
- [x] Create EcosystemCanvas with R3F Canvas
- [x] Create SystemNode with Platonic solid geometries (icosahedron/octahedron/dodecahedron)
- [x] Create NodeLabel with Html overlay
- [x] Create FlowEdge with curved bezier lines
- [x] Create growth tier system (Seed/Active/Established/Mature/Complex)
- [x] Wire data from API to 3D scene via useEcosystem hook
- [x] Click node navigates to /nodes/{nodeId} detail page

#### Phase 7d: Node Detail Pages
- [x] Create /nodes/[nodeId] page with metrics, breakdown, recent records
- [x] Back navigation to ecosystem view

#### Phase 7e: Agents Section
- [x] Create AgentCard grid with category badges
- [x] Create PersonaDetail with identity, voice, frameworks, case studies, metadata
- [x] Dynamic route /agents/[agentId]

#### Phase 7f: Pipeline Status
- [x] Create PipelineStatus stage funnel visualization
- [x] Ideas list with stage/status badges, scores, tags

#### Phase 7g: Growth System
- [x] Node tier calculation (0-4 based on record count)
- [x] Edge state calculation (dormant/active/busy/saturated)
- [x] Visual effects: wireframe for Seed, solid for Active+, scale/glow by tier
- [ ] Animated tier transitions (springs)

### Phase 8: Loop Verification (End-to-End)
- [x] Data integrity: Remove duplicate OutcomeRecord for idea #5
- [x] Data integrity: Remove dry-run test artifact from recommendations
- [x] Fix rebuild_sqlite() — was re-appending to JSONL (critical bug)
- [x] Fix loop_status.py — switch from JSONL (immutable) to SQLite (status-aware)
- [x] Fix query_recommendations/query_patches — overlay SQLite status onto raw_json
- [x] Fix recommendation dedup in report_writer.py (session_id check)
- [x] Remove conflicting /etc/cron.d/sky-lynx (st-records cron already calls SL)
- [x] Add env sourcing to run_loop.sh for cron robustness
- [x] Create review_patch.py HIL tool (list/show/apply/reject)
- [x] Apply patch-c6495783 (user_adoption_journey framework to sky-lynx)
- [x] Validate updated persona passes Academy schema
- [x] Exercise persona_upgrader -> review -> reject path (patch-4564f91b)
- [x] Verify loop_status shows completed cycles >= 1
- [x] Test cron environment (stripped env dry-run passes)
- [x] Add logrotate for /var/log/st-records/loop.log
- [x] Commit changes across repos

#### Phase 7h: WebXR / VR Mode (Deferred)
VR placeholder files removed. @react-three/xr removed from deps. Revisit when Quest 3 testing is practical.
- [ ] VRButton component (Enter VR when WebXR available)
- [ ] VRScene with XR provider wrapping existing scene
- [ ] VRLocomotion (teleport movement)
- [ ] VRNodeInteractor (controller-based detail panels)

### Phase 9: A2A Protocol Integration (Future)
- [ ] Evaluate A2A spec against ST Metro agent communication needs
- [ ] Define Agent Cards for ecosystem agents (Metroplex, YCE Harness, Sky-Lynx, ClaudeClaw)
- [ ] Expose ContractStore operations as A2A task endpoints (via FastAPI)
- [ ] ClaudeClaw (Data) as first A2A peer -- ops task delegation
- [ ] Metroplex as A2A coordinator -- dispatch tasks to any A2A-compliant agent
- [ ] Agent discovery via `.well-known/agent.json`
- [ ] Bidirectional task delegation between future agents

**Prerequisite**: Stable end-to-end loop (Phase 8 -- DONE), Metroplex Priority Queue operational (ST Metro Phase 9).
**Rationale**: As more agents are added to the ecosystem, A2A provides model-agnostic, framework-agnostic agent interop. MCP handles tool augmentation; A2A handles peer-to-peer coordination between independent agents.

#### Phase 7i: Polish & Documentation
- [x] Update .gitignore for dashboard artifacts
- [ ] Visual tuning (lighting, colors, animation curves)
- [ ] Performance profiling for Quest 3
- [ ] generate_test_data.py script
- [ ] dashboard/README.md
- [ ] decisions.log entries
