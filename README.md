# Prior-Auth Clearance Agent -- Learning Build

A hands-on build of the pipeline from the whiteboard diagram: ingestion ->
validation/agent loop -> RAG enrichment -> decision engine (guardrails +
confidence routing) -> orchestration (resumable workflow) -> observability.

## How this is meant to work

Each module under `src/` has function/class signatures, type hints, and a
docstring describing the exact contract, but no implementation -- they
raise `NotImplementedError` or don't exist yet. Each implemented phase has
a matching test file under `tests/` that defines the expected behavior in
executable form. Implement against the tests until they pass, then stop
and bring the code back for review before starting the next phase.

Passing the happy-path tests is the floor, not the target. Each phase
below has an engineering bar attached -- that's the actual thing being
practiced.

## Setup

```
python -m venv venv
source venv/bin/activate      # venv\Scripts\activate on Windows
pip install -r requirements.txt
pytest -v
```

Everything currently fails with `NotImplementedError`. That's expected --
it means the scaffold and tests are wired up correctly.

## Phases

### Phase 1 -- Reliability layer (`src/reliability/`) -- START HERE
Build `retry_with_backoff` and `CircuitBreaker` from scratch. No
`tenacity`, no shortcuts. Every external call the rest of the system
makes (LLM calls, tool calls, retrieval calls) will sit behind this.

Engineering bar: exponential backoff with jitter, a hard max-attempts
ceiling, circuit opens after N consecutive failures and rejects calls
outright while open (without even trying the underlying call), and a
half-open probe after a cooldown period.

### Phase 2 -- Ingestion (`src/ingestion/`)
Parse and validate a raw prior-auth request into a typed
`PriorAuthRequest`. The Pydantic schema (`models.py`) is provided as
given -- the work is in `parser.py`.

Engineering bar: real, actionable validation errors ("missing required
field: provider_npi"), not a bare "invalid input."

### Phase 3 -- Agent loop (`src/agent/`) -- not scaffolded yet
Build a bare-metal agent loop (no LangChain yet) that figures out what's
missing from a validated request and calls tools to fetch it.

Engineering bar: the loop has to survive a tool that times out and a
tool that returns malformed data, using the Phase 1 reliability layer.
We'll scaffold this phase together once Phase 1-2 are done and reviewed.

### Phase 4 -- RAG enrichment (`src/rag/`) -- not scaffolded yet
Retrieve relevant payer policy text to support the decision.

Engineering bar: chunking tied to document structure (not fixed
character counts), hybrid search (keyword + vector, not vector-only),
a reranking step, and a measured precision/recall check against
`data/policy_docs/` -- not just "it returns something plausible."

### Phase 5 -- Decision engine (`src/decision/`) -- not scaffolded yet
Score confidence and emit a structured approve/deny/route-to-human
decision.

Engineering bar: a repair loop for invalid LLM output (feed the
validation error back to the model, don't just discard and fail), plus
guardrail tests -- e.g. "confidence > 0.95 must never route to human
review."

### Phase 6 -- Orchestration (`src/orchestration/`) -- not scaffolded yet
Make the workflow resumable: checkpoint state after each step so a
crash or restart doesn't start the whole request over.

### Phase 7 -- Observability (`src/observability/`) -- not scaffolded yet
Structured, replayable tracing per step -- input, tool calls,
intermediate reasoning, output -- so a bad decision can actually be
debugged after the fact.

## Working loop

1. Implement the current phase in Cursor/VS Code.
2. Run `pytest -v` for that module until it's green.
3. Bring the code back for review before scaffolding the next phase --
   review is for architecture and edge cases, not just "did tests pass."

`data/sample_requests/` has fixtures for Phase 2. `data/policy_docs/`
has placeholder documents for Phase 4, once we get there.
