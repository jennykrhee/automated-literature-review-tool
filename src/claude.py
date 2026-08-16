from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
import anthropic


class ClaudeScorer:
    def __init__(self, prompt_path: Path):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")
        self.system_prompt = prompt_path.read_text(encoding="utf-8")

    def score(self, profile: dict[str, Any], paper: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "research_profile": profile,
            "paper": {
                "title": paper.get("title"),
                "abstract": paper.get("abstract", ""),
                "journal": paper.get("journal"),
                "publication_date": paper.get("publication_date"),
                "authors": paper.get("authors", []),
                "doi": paper.get("doi"),
                "topics": paper.get("topics", []),
            },
        }
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=3000,
            system=self.system_prompt,
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        )
        text = "".join(getattr(block, "text", "") for block in msg.content)




        print("\n===== RAW CLAUDE RESPONSE =====")
        print(text)
        print("===== END RAW RESPONSE =====\n")


        start = text.find("{")
        end = text.rfind("}")

        if start < 0 or end < start:
            raise ValueError(f"Claude did not return JSON: {text[:500]}")

        return json.loads(text[start:end + 1])








        #start = text.find("{")
        #end = text.rfind("}")
        #if start < 0 or end < start:
         #   raise ValueError(f"Claude did not return JSON: {text[:500]}")
        #return json.loads(text[start:end + 1])
