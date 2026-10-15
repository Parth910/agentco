"""End-to-end check that the configured LLM works: plain chat + structured output.

Run inside the container with `make llm-test` (or `./agentco llm-test`).
"""

import sys

from pydantic import BaseModel

from agentco.llm import LLMClient, StructuredOutputError


class ProductIdea(BaseModel):
    name: str
    features: list[str]


def main() -> int:
    client = LLMClient()
    cfg = client.config
    print(f"Model: {cfg.model} @ {cfg.base_url} (reasoning_effort={cfg.reasoning_effort or 'unset'})\n")

    try:
        r = client.chat("Reply with exactly: AgentCo is online.")
        print(f"✔ Chat        {r.latency_s:>6.2f}s  {r.completion_tokens:>4} tokens  → {r.text.strip()}")

        s = client.structured(
            "Suggest a name and 3 short features for a social feed app for college students.",
            ProductIdea,
        )
        r = s.response
        print(f"✔ Structured  {r.latency_s:>6.2f}s  {r.completion_tokens:>4} tokens  → {s.data.name}")
        for feature in s.data.features:
            print(f"    - {feature}")
        if s.attempts > 1:
            print(f"  (needed {s.attempts} attempts)")
    except StructuredOutputError as exc:
        print(f"✘ Structured output failed: {exc}")
        return 1
    except Exception as exc:  # connection errors, missing model, etc.
        print(f"✘ LLM call failed: {exc}")
        return 1

    print("\nLLM client OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
