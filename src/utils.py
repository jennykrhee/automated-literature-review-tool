from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def read_yaml(path: Path) -> dict[str, Any]:
    import yaml
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).strip().lower()
    text = re.sub(r"[-\s]+", "-", text)
    return text[:140] or "untitled-paper"


def abstract_from_inverted_index(inv: dict[str, list[int]] | None) -> str:
    if not inv:
        return ""
    words = []
    for token, positions in inv.items():
        for pos in positions:
            words.append((pos, token))
    words.sort()
    return " ".join(token for _, token in words)
