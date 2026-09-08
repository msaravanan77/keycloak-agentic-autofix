# Keycloak Bug-Fix Multi-Agent Project — Discussion Summary

## 1. Origin & Framework
- Started from the AWS sample repo `sample-once-upon-agentic-ai`, a workshop teaching the **Strands Agents SDK** (an AWS agentic-AI framework), structured as 5 chapters: agent basics → built-in tools → custom tools (`@tool`) → MCP integration → A2A (agent-to-agent).
- Goal: apply Strands to a real use case — an autonomous **bug discovery → fix → review → PR** pipeline against the real Keycloak GitHub repo.

## 2. Architecture — Evolution
1. **First hand-drawn diagram** (paper sketch): a 9-step linear flow — clone repo → get bug list → human picks bug → fix → doc → test → review (loop back if rejected) → create PR → inform user.
2. **First digital version**: flat sequence of colored boxes — flagged as too "amateur," poor contrast, no grouping.
3. **Layered structural version**: grouped into 3 phases — **Orchestrator layer** (workflow controller + human checkpoint) → **Specialized agents** (grouped by discovery/authoring vs. verification) → **Delivery** (PR agent + notify) → **Output**. Styled after a professional JVM-internals reference diagram, first on adaptive (dark-mode-safe) colors, then rebuilt on a **fixed white background** with hardcoded hex colors per the user's explicit request.
4. **Final refinement**: added *internal* sequential arrows inside "Specialized agents" (scanner → coder → doc → test → reviewer) plus a solid "approved" exit arrow and a dashed "changes needed" loop-back arrow to the coder agent — addressing feedback that agents looked isolated rather than handing off work.

**Color key used throughout:** blue = orchestration/control, purple = discovery & authoring agents, teal/green = verification agents, orange/coral = delivery/git-facing agents, gray = structural grouping & I/O.

## 3. Decision: Where to Start
- Chosen first agent: **Bug scanner agent** — lowest risk (read-only, no repo writes), easiest to validate against ground truth, and it defines the output contract every downstream agent depends on.
- Real-world starting point confirmed: Keycloak tracks issues on GitHub (not Jira), uses a `good first issue` label, and has a `CONTRIBUTING.md` with Java/Quarkus/Maven build requirements.

## 4. Model / Auth Setup
- Strands' default model provider is **Amazon Bedrock** (Claude Sonnet, `global.anthropic.claude-sonnet-4-6` by default) — not a raw OpenAI/Anthropic API key.
- Simplest auth path chosen: **Amazon Bedrock API key** (bearer token) generated from the AWS Console (Bedrock → API keys → service "Amazon Bedrock" → **long-term** key, since short-term expires in ≤12h).
- Required env vars:
  ```
  AWS_BEARER_TOKEN_BEDROCK=<key>
  AWS_REGION=us-east-1
  ```
- **Gotcha #1:** `.env` is not auto-loaded by Python — must explicitly `pip install python-dotenv` and call `load_dotenv()` **before** importing/using `strands`, or boto3 silently falls back to bad credentials and throws `UnrecognizedClientException: security token invalid`. This bug recurred once when a rewritten file accidentally dropped the `load_dotenv()` call — root-caused and fixed the same way.
- **Gotcha #2:** running `python3 agents/bug_scanner_agent.py` directly fails with `ModuleNotFoundError: No module named 'tools'` because sibling packages aren't on the path. Fix: run as a module from project root — `python3 -m agents.bug_scanner_agent`.
- Model is explicitly pinned (not left as an implicit SDK default) via `config/settings.py: MODEL_ID` and passed into `BedrockModel(model_id=MODEL_ID)`.

## 5. Project Structure (agreed convention)
```
keycloak-bugfix-agent/
├── .env                          # AWS_BEARER_TOKEN_BEDROCK, AWS_REGION, GITHUB_TOKEN
├── pyproject.toml                # deps: requests, strands-agents, python-dotenv, pydantic
├── poc/                          # throwaway/exploratory scripts only, dated filenames, never imported by real code
│   └── 2026-09-08_github_search_api_check.py
├── config/
│   ├── settings.py                # REPO_NAME, MODEL_ID, DEFAULT_ISSUE_LIMIT
│   └── system_prompts/
│       └── bug_scanner.md         # done
│       # coder.md, doc_writer.md, tester.md, reviewer.md, pr_agent.md — pending
├── tools/
│   └── github_issues.py           # done — fetch_good_first_issues @tool
│       # git_ops.py, code_editor.py, test_runner.py, keycloak_auth.py — pending
├── agents/
│   └── bug_scanner_agent.py       # done — agent + structured JSON extraction
│       # coder_agent.py, doc_agent.py, test_agent.py, reviewer_agent.py, pr_agent.py — pending
├── models/
│   └── schemas.py                 # done — Issue, BugScanResult (pydantic)
├── orchestrator/                  # pending — workflow.py, human_checkpoint.py
└── tests/
    └── test_bug_scanner.py        # drafted
```
Rule of thumb agreed: anything exploratory/"let me just check if this works" → `poc/`, dated, never wired into real imports.

## 6. Bug Scanner Agent — Final Working Design
- **Tool** (`tools/github_issues.py`): calls GitHub's public search API for `label:"good first issue"`, returns `number, title, url, comments, labels` per issue (labels added specifically to give the model real signal instead of guessing from titles).
- **Prompt** (`config/system_prompts/bug_scanner.md`) iterated three times:
  1. v1 — general "find and rank bugs."
  2. v2 — restricted to backend/Java areas via label examples, added anti-padding rule ("return fewer rather than padding") and anti-retry rule (stop calling the tool twice for the same data — this had been wasting tokens on a redundant identical fetch).
  3. v3 (final) — explicitly required the `kind/bug` label and explicitly excluded `kind/enhancement`/`kind/task`/`kind/feature`, since the model had been loosely including enhancements as if they were bugs.
- **Structured output contract**: agent emits a human-readable summary *and* one trailing fenced ```json block matching `models/schemas.py:BugScanResult`, parsed via regex + pydantic validation in `agents/bug_scanner_agent.py:extract_bug_scan_result()`. Chosen deliberately over Strands' native structured-output mode so both a human-facing answer and a machine-facing contract coexist in one response — the human checkpoint step reads the prose, downstream agents read the JSON.
- **Validated live run**: real GitHub data → agent → filtered to genuine backend Java bugs → valid parsed JSON. Token usage per run ≈ 3,700–8,800 tokens (~$0.01–$0.05 per run at Bedrock Claude Sonnet pricing).

## 7. Cost/Usage Monitoring
- Fastest per-run check (no AWS lag): `result.metrics.accumulated_usage` printed directly from the Strands `Agent` call.
- AWS-side check: `aws ce get-cost-and-usage` filtered by `SERVICE=Amazon Bedrock` (needs `ce:GetCostAndUsage` IAM permission, which the Bedrock API key alone does **not** grant) — or Console → Cost Explorer. Both have a ~24h reporting lag.

## 8. Outstanding / Next Steps
- Re-run the bug scanner once more to confirm the `kind/bug`-only tightening drops enhancement issues as intended.
- Build the **human checkpoint** step next (human selects one issue number from the structured output).
- Then proceed agent-by-agent down the pipeline: Coder → Doc → Test → Reviewer (with the approve/reject loop) → PR agent.
- Still open: whether to add a max-retry cap on the reviewer's reject-loop (flagged early as a design gap, not yet implemented).