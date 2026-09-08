import json
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from strands import Agent
from strands.models import BedrockModel

from tools.github_issues import fetch_good_first_issues
from config.settings import MODEL_ID, REPO_NAME
from models.schemas import BugScanResult

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SYSTEM_PROMPT = (PROJECT_ROOT / "config" / "system_prompts" / "bug_scanner.md").read_text()

model = BedrockModel(model_id=MODEL_ID)

bug_scanner = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[fetch_good_first_issues],
)


def extract_bug_scan_result(agent_response_text: str) -> BugScanResult:
    """Pull the last ```json fenced block out of the agent's response and validate it.

    Anchors on the final ```json fence and its closing ```, so nested braces and
    any stray prose after the block don't break parsing.
    """
    marker = "```json"
    start = agent_response_text.rfind(marker)
    if start == -1:
        raise ValueError("No JSON block found in agent response")
    start += len(marker)
    end = agent_response_text.find("```", start)
    if end == -1:
        raise ValueError("Unterminated JSON block in agent response")
    data = json.loads(agent_response_text[start:end].strip())
    return BugScanResult.model_validate(data)


if __name__ == "__main__":
    result = bug_scanner(f"Find the best good-first-issue backend Java bugs in {REPO_NAME}")
    print(result)
    print(result.metrics.accumulated_usage)

    structured = extract_bug_scan_result(str(result))
    print("\n--- Parsed structured result ---")
    print(structured.model_dump_json(indent=2))
