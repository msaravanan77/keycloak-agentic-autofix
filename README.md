# keycloak-agentic-autofix

An autonomous, multi-agent pipeline that discovers a real bug in the
[Keycloak](https://github.com/keycloak/keycloak) repository, fixes it, documents
and tests the fix, puts it through an automated review loop, and opens a pull
request — with a human checkpoint at the start.

Built on the [Strands Agents SDK](https://github.com/strands-agents/sdk-python)
and Amazon Bedrock (Claude Sonnet). It began as an exercise on top of the
`sample-once-upon-agentic-ai` workshop and grew into a full end-to-end use case:
applying agentic AI to the unglamorous, high-value task of triaging and fixing
"good first issue" bugs in a large Java codebase.

> A write-up walking through the design decisions and what worked / didn't is
> planned. This repo is the reference implementation for it.

---

## Pipeline

```
                        ┌─────────────────────────────────────────┐
   Orchestrator layer   │  workflow controller  ·  human checkpoint │
                        └─────────────────────────────────────────┘
                                          │  (human picks one issue)
                                          ▼
   Specialized agents   scanner ─▶ coder ─▶ doc ─▶ test ─▶ reviewer
                                     ▲                        │
                                     └──── changes needed ────┘   (approved ▼)
                                          
   Delivery             pr agent  ─▶  notify user
```

| Stage | Agent | Role | Writes to repo? |
|-------|-------|------|-----------------|
| Discovery | **bug scanner** | Pull open `good first issue` tickets, keep only genuine backend-Java `kind/bug` issues, emit a structured shortlist | no |
| — | **human checkpoint** | Human selects one issue number from the shortlist | no |
| Authoring | **coder** | Produce a fix for the selected issue | branch |
| Authoring | **doc writer** | Update changelog / docs for the fix | branch |
| Verification | **tester** | Add or run tests covering the fix | branch |
| Verification | **reviewer** | Approve, or send it back to the coder with change requests (capped loop) | no |
| Delivery | **pr agent** | Push the branch and open a PR against Keycloak | fork + PR |

---

## Status

Being built agent-by-agent, discovery-first (read-only, lowest risk, and it
defines the output contract every downstream agent consumes).

| Component | State |
|-----------|-------|
| `tools/github_issues.py` — `fetch_good_first_issues` | ✅ done, validated live |
| `models/schemas.py` — `Issue`, `BugScanResult` | ✅ done |
| `config/settings.py`, `config/system_prompts/bug_scanner.md` | ✅ done |
| `agents/bug_scanner_agent.py` — agent + structured-output extraction | ✅ done, validated end-to-end |
| `tests/test_bug_scanner.py` | ✅ passing |
| human checkpoint, coder, doc, tester, reviewer, pr agent | ⬜ scaffolded, not implemented |
| `orchestrator/workflow.py` | ⬜ not implemented |

### Roadmap

1. Decide the reviewer reject-loop cap (max coder↔reviewer rounds before escalating to a human).
2. **Human checkpoint** — read `BugScanResult`, present issues, read a chosen number.
3. **Issue-detail tool** — `fetch_issue_detail(number)` for the full body + comments + linked PRs.
4. **`tools/git_ops.py`** — shallow-clone / checkout Keycloak, create a branch.
5. **Coder agent** — first version produces a reviewed patch (code search + read + edit, no build); real `mvn` compile/test comes later as its own milestone.
6. Doc → Tester → Reviewer (capped loop) → PR agent, each validated live like the scanner was.
7. **`orchestrator/workflow.py`** — wire the agents together (agents-as-tools / graph pattern).

---

## Quickstart

Requires Python 3.10+ and an Amazon Bedrock **long-term** API key (short-term
keys expire in <12h).

```bash
pip install -e .            # or: pip install strands-agents requests pydantic python-dotenv boto3
cp .env.example .env        # then fill in your values
```

`.env`:

```
AWS_BEARER_TOKEN_BEDROCK=<your-bedrock-long-term-api-key>
AWS_REGION=us-east-1
GITHUB_TOKEN=<optional-now-required-for-the-pr-agent>
```

Run the bug scanner (from the project root, as a module):

```bash
python3 -m agents.bug_scanner_agent
```

It prints a human-readable shortlist, the token usage for the run, and the
parsed `BugScanResult`. Typical run: ~3.7k tokens (~$0.01 at Bedrock Claude
Sonnet pricing).

### Tests

```bash
pip install -e ".[dev]"
pytest
```

`test_fetch_returns_list_of_issues` hits the live GitHub search API;
`test_extract_handles_nested_braces_and_trailing_prose` is offline.

---

## Project layout

```
keycloak-agentic-autofix/
├── .env.example              # required env vars (copy to .env)
├── pyproject.toml            # deps: strands-agents, requests, pydantic, python-dotenv, boto3
├── config/
│   ├── settings.py           # REPO_NAME, DEFAULT_ISSUE_LIMIT, MODEL_ID
│   └── system_prompts/       # one .md system prompt per agent
├── tools/                    # @tool functions the agents call (github, git, editor, tests)
├── agents/                   # one Strands Agent per pipeline stage
├── models/schemas.py         # pydantic contracts passed between agents
├── orchestrator/             # workflow controller + human checkpoint
├── tests/
└── poc/                      # dated throwaway spikes, never imported by real code
```

---

## Design notes

- **Model is pinned**, not left to the SDK default: `config/settings.py:MODEL_ID`
  (`global.anthropic.claude-sonnet-4-6`), passed into `BedrockModel(model_id=...)`.
- **`load_dotenv()` runs before any `strands` import.** Skip it and boto3
  silently falls back to bad credentials and throws
  `UnrecognizedClientException: security token invalid`.
- **Run agents as modules** (`python3 -m agents.bug_scanner_agent`) so sibling
  packages resolve; running the file directly fails with `ModuleNotFoundError`.
- **Structured output by convention, not SDK mode.** The scanner emits a
  human-readable summary *and* one trailing ```` ```json ```` block matching
  `models/schemas.py:BugScanResult`, parsed by
  `agents/bug_scanner_agent.py:extract_bug_scan_result()`. The human checkpoint
  reads the prose; downstream agents read the JSON.
- **Per-run cost check:** `result.metrics.accumulated_usage` — instant, no AWS
  reporting lag.
