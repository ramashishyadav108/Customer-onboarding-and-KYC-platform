"""Programmatic Claude Agent SDK usage: run a read-only spec-vs-code review.

Usage: python scripts/agent_review.py [sprint-label]
Requires: pip install claude-agent-sdk (and ANTHROPIC_API_KEY or Claude Code login).
Writes the agent's findings to specs/reviews/sdk-review-<label>.md.
"""
import asyncio
import sys
from pathlib import Path

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query

PROMPT = (
    "Read specs/app_spec.md and specs/*_spec.md. For every AC-NN and NFR-NN id, "
    "grep the tests for a reference and list ids with no test. "
    "Report only; do not modify any file."
)


async def main(label: str) -> None:
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Grep", "Glob"],
        permission_mode="default",
        cwd=str(Path(__file__).resolve().parent.parent),
    )
    chunks: list[str] = []
    async for message in query(prompt=PROMPT, options=options):
        if isinstance(message, AssistantMessage):
            chunks.extend(b.text for b in message.content if isinstance(b, TextBlock))

    out = Path("specs/reviews") / f"sdk-review-{label}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(chunks), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "latest"))
