from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any
import os
import requests


def md_escape(text: str) -> str:
    return str(text).replace("|", "\\|")


def write_note(vault: Path, folder: str, filename: str, content: str) -> Path:
    path = vault / folder / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def write_radar(vault: Path, radar_folder: str, literature_folder: str, papers: list[dict[str, Any]], run_date: date) -> Path:
    rows = sorted(papers, key=lambda x: x.get("score", {}).get("overall_relevance", 0), reverse=True)
    lines = [f"# Literature Radar — {run_date.isoformat()}", "", f"Found **{len(rows)}** new candidate papers.", ""]

    for label, predicate in [
        ("READ NOW", lambda s: s.get("priority") == "READ NOW"),
        ("SKIM", lambda s: s.get("priority") == "SKIM"),
        ("LOW PRIORITY", lambda s: s.get("priority") == "LOW PRIORITY"),
    ]:
        group = [p for p in rows if predicate(p.get("score", {}))]
        lines += [f"## {label}", ""]
        if not group:
            lines += ["None.", ""]
        else:
            for p in group:
                s = p.get("score", {})
                title = p["title"]
                note_name = p.get("note_filename", "")
                lines.append(f"### [{title}]({literature_folder}/{run_date.year}/{note_name})")
                lines.append(f"**Journal:** {md_escape(p.get('journal', ''))}  ")
                lines.append(f"**Published:** {p.get('publication_date', '')}  ")
                lines.append(f"**Relevance:** **{s.get('overall_relevance', 0)}/100**  ")
                lines.append(f"**Why:** {s.get('potential_connection', '')}")
                if s.get("why_relevant"):
                    lines.append("")
                    for reason in s["why_relevant"]:
                        lines.append(f"- {reason}")
                if s.get("research_question_seed"):
                    lines.append("")
                    lines.append(f"**Research-question seed:** {s['research_question_seed']}")
                lines.append("")

    path = vault / radar_folder / f"{run_date.isoformat()}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def maybe_write_via_rest(folder: str, filename: str, content: str) -> bool:
    base = os.environ.get("OBSIDIAN_REST_URL")
    key = os.environ.get("OBSIDIAN_REST_API_KEY")
    if not base or not key:
        return False
    path = f"{folder.strip('/')}/{filename}"
    url = base.rstrip("/") + "/vault/" + path
    r = requests.put(
        url,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "text/markdown"},
        data=content.encode("utf-8"),
        verify=False,
        timeout=30,
    )
    r.raise_for_status()
    return True
