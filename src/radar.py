from __future__ import annotations

import argparse
import os
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

from .claude import ClaudeScorer
from .obsidian import md_escape, write_note, write_radar
from .openalex import fetch_recent_works, find_source
from .utils import abstract_from_inverted_index, append_jsonl, read_jsonl, read_yaml, slugify


ROOT = Path(__file__).resolve().parents[1]


def normalize_work(work: dict, journal: str) -> dict:
    authors = []
    for a in work.get("authorships", []):
        name = a.get("author", {}).get("display_name")
        if name:
            authors.append(name)
    source = (work.get("primary_location") or {}).get("source") or {}
    doi = work.get("doi") or work.get("ids", {}).get("doi")
    return {
        "openalex_id": work.get("id"),
        "doi": doi,
        "title": work.get("display_name") or work.get("title") or "Untitled",
        "abstract": abstract_from_inverted_index(work.get("abstract_inverted_index")),
        "journal": journal,
        "publication_date": work.get("publication_date"),
        "publication_year": work.get("publication_year"),
        "authors": authors,
        "landing_page": (work.get("primary_location") or {}).get("landing_page_url"),
        "pdf_url": (work.get("primary_location") or {}).get("pdf_url"),
        "is_oa": (work.get("open_access") or {}).get("is_oa"),
        "cited_by_count": work.get("cited_by_count", 0),
        "topics": [t.get("display_name") for t in work.get("topics", []) if t.get("display_name")],
        "source": source.get("display_name"),
    }


def paper_key(p: dict) -> str:
    return (p.get("doi") or p.get("openalex_id") or (p.get("title", "") + "|" + p.get("journal", ""))).lower()




def cheap_prefilter(p: dict, profile: dict) -> bool:
    text = " ".join([
        p.get("title", ""),
        p.get("abstract", ""),
        " ".join(p.get("topics", [])),
    ]).lower()

    def matches(items):
        return sum(
            1 for item in items
            if item.lower() in text
        )

    topic_hits = (
        matches(profile.get("core_topics", []))
        + matches(profile.get("phenomena", []))
        + matches(profile.get("mechanisms_and_theories", []))
        + matches(profile.get("contexts", []))
        + matches(profile.get("benchmark_research", []))
    )

    method_hits = matches(profile.get("methods", []))

    negative_hits = matches(profile.get("negative_signals", []))

    if negative_hits >= 2 and topic_hits < 2:
        return False

    return topic_hits >= 2 or (topic_hits >= 1 and method_hits >= 1)






def make_note(p: dict) -> str:
    s = p["score"]
    authors = ", ".join(p.get("authors", []))
    why = "\n".join(f"- {x}" for x in s.get("why_relevant", [])) or "- None identified."
    borrow = "\n".join(f"- {x}" for x in s.get("what_to_borrow", [])) or "- None identified."
    projects = "\n".join(f"- {x}" for x in s.get("closest_existing_projects", [])) or "- None."
    cautions = "\n".join(f"- {x}" for x in s.get("cautions", [])) or "- None."
    return f'''---\ntitle: "{p['title'].replace(chr(34), "'")}"\njournal: "{p.get('journal', '').replace(chr(34), "'")}"\npublished: {p.get('publication_date') or ''}\ndoi: "{p.get('doi') or ''}"\noverall_relevance: {s.get('overall_relevance', 0)}\npriority: "{s.get('priority', '')}"\n---\n\n# {p['title']}\n\n**Journal:** {p.get('journal', '')}\n\n**Authors:** {authors}\n\n**Published:** {p.get('publication_date', '')}\n\n**DOI:** {p.get('doi') or 'N/A'}\n\n**Relevance:** {s.get('overall_relevance', 0)}/100\n\n## Why this is relevant\n{why}\n\n## Closest active projects\n{projects}\n\n## Potential connection\n{s.get('potential_connection', '')}\n\n## What to borrow\n{borrow}\n\n## Research-question seed\n{s.get('research_question_seed', '')}\n\n## Cautions\n{cautions}\n\n## Abstract\n{p.get('abstract') or 'Abstract not available from OpenAlex.'}\n\n## Links\n\n{p.get('landing_page') or ''}\n'''


def main() -> None:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", type=int, default=None, help="Days back to search")
    parser.add_argument("--from", dest="from_date", type=lambda x: date.fromisoformat(x),
                        help="Start date, YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", type=lambda x: date.fromisoformat(x),
                        help="End date, YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=None,
                        help="Maximum number of papers to process")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--test", action="store_true", help="Score papers with Claude and print results without saving to JSONL or Obsidian")
    parser.add_argument("--select", nargs="+", default=None, help="Select papers by title keywords")
    parser.add_argument("--title", action="append", default=None, help="Select an exact paper title; can be used multiple times")
    args = parser.parse_args()

    journals_cfg = read_yaml(ROOT / "config/journals.yaml")
    profile = read_yaml(ROOT / "config/research_profile.yaml")
    journals = journals_cfg.get("journals", [])
    email = os.environ.get("OPENALEX_EMAIL", "")
    openalex_key = os.environ.get("OPENALEX_API_KEY", "")
    if not openalex_key:
        raise RuntimeError("OPENALEX_API_KEY is not set. Get a key at https://openalex.org/settings/api")

    existing = read_jsonl(ROOT / "data/papers.jsonl")
    existing_keys = {paper_key(p) for p in existing}
    discovered = []
    prefiltered_out = 0
    already_seen = 0
    total_retrieved = 0

    if args.from_date and args.to_date:
        start = args.from_date
        end = args.to_date
    elif args.since is not None:
        start = date.today() - timedelta(days=args.since)
        end = date.today()
    else:
        start = date.today() - timedelta(days=7)
        end = date.today()
    for journal in journals:
        source = find_source(journal, email=email, api_key=openalex_key)
        if not source:
            print(f"[WARN] Journal not found: {journal}")
            continue
        source_id = source["id"].rstrip("/").split("/")[-1]
        print(f"[INFO] Checking {journal} ({source_id})")
        for work in fetch_recent_works(
            source_id,
            start_date=start,
            end_date=end,
            email=email,
            api_key=openalex_key
        ):
            total_retrieved += 1
            p = normalize_work(work, journal=journal)

            if args.title:
                if p["title"] not in args.title:
                    continue

            else:
                if not cheap_prefilter(p, profile):
                    prefiltered_out += 1
                    continue

            key = paper_key(p)


            if key in existing_keys:
                already_seen += 1
                continue
            
            if args.select:
                title_lower = p["title"].lower()

                if not any(
                    keyword.lower() in title_lower
                    for keyword in args.select
                ):
                    continue

            if not p.get("abstract"):
                # Keep metadata-only records, but do not spend an LLM call on an empty abstract.
                p["score"] = {
                    "overall_relevance": 0,
                    "priority": "LOW PRIORITY",
                    "why_relevant": ["No abstract was available from OpenAlex for automated assessment."],
                    "closest_existing_projects": [],
                    "closest_research_areas": [],
                    "potential_connection": "Insufficient text for a reliable relevance assessment.",
                    "what_to_borrow": [],
                    "research_question_seed": "",
                    "cautions": ["Manual review required."],
                    "active_project_scores": [],
                }
            else:
                p["score"] = None
            discovered.append(p)
            existing_keys.add(key)
            if args.limit and len(discovered) >= args.limit:
                break
        if args.limit and len(discovered) >= args.limit:
                break
    print(f"[INFO] Total papers retrieved: {total_retrieved}")
    print(f"[INFO] Excluded by cheap pre-filter: {prefiltered_out}")
    print(f"[INFO] Already in library: {already_seen}")
    print(f"[INFO] New papers sent to Claude: {len(discovered)}")

    if not discovered:
        print("[INFO] No new papers found.")
        return

    scorer = None if args.dry_run else ClaudeScorer(ROOT / "prompts/relevance.md")
    for p in discovered:
        if p["score"] is None:
            print(f"[INFO] Scoring: {p['title']}")
            p["score"] = scorer.score(profile, p) if scorer else {
                "overall_relevance": 0,
                "priority": "LOW PRIORITY",
                "why_relevant": [],
                "closest_existing_projects": [],
                "closest_research_areas": [],
                "potential_connection": "Dry run.",
                "what_to_borrow": [],
                "research_question_seed": "",
                "cautions": [],
                "active_project_scores": [],
            }

    if args.dry_run:
        for p in discovered:
            print(f"{p['title']} | {p['journal']} | {p['publication_date']} | {p['score']['overall_relevance']}")
        return

    if args.test:
        print("\n" + "=" * 80)
        print("CLAUDE SCORING TEST RESULTS")
        print("=" * 80)

        for p in sorted(
            discovered,
            key=lambda x: x["score"].get("overall_relevance", 0),
            reverse=True
        ):
            s = p["score"]

            print(f"\nTITLE: {p['title']}")
            print(f"JOURNAL: {p['journal']}")
            print(f"DATE: {p.get('publication_date', '')}")
            print(f"OVERALL: {s.get('overall_relevance', 0)}/100")
            print(f"PRIORITY: {s.get('priority', '')}")

            print(
                "DIMENSIONS: "
                f"topic={s.get('topic_relevance', 0)}, "
                f"phenomenon={s.get('phenomenon_relevance', 0)}, "
                f"theory={s.get('theory_mechanism_relevance', 0)}, "
                f"method={s.get('method_relevance', 0)}, "
                f"context={s.get('context_data_relevance', 0)}, "
                f"novelty={s.get('novelty_research_potential', 0)}"
            )

            print("WHY RELEVANT:")
            for reason in s.get("why_relevant", []):
                print(f"  - {reason}")

            print("ACTIVE PROJECTS:")
            for project in s.get("active_project_scores", []):
                print(
                    f"  - {project.get('project', '')}: "
                    f"{project.get('score', 0)}/100"
                )
                print(f"    {project.get('reason', '')}")

            print(f"POTENTIAL CONNECTION: {s.get('potential_connection', '')}")

            print("WHAT TO BORROW:")
            for item in s.get("what_to_borrow", []):
                print(f"  - {item}")

            print(
                "RESEARCH QUESTION SEED: "
                f"{s.get('research_question_seed', '')}"
            )

            print("CAUTIONS:")
            for caution in s.get("cautions", []):
                print(f"  - {caution}")

            print("-" * 80)

        print("\n[TEST] Nothing was saved to papers.jsonl or Obsidian.")
        return

    append_jsonl(ROOT / "data/papers.jsonl", discovered)

    vault = Path(os.environ.get("OBSIDIAN_VAULT_PATH", "")).expanduser()
    radar_folder = os.environ.get("OBSIDIAN_RADAR_FOLDER", "Literature Radar")
    literature_folder = os.environ.get("OBSIDIAN_LITERATURE_FOLDER", "Literature")
    if not vault.exists():
        raise RuntimeError("OBSIDIAN_VAULT_PATH is missing or does not exist. Set it in .env")

    for p in discovered:
        p["note_filename"] = slugify(p["title"]) + ".md"
        year_folder = f"{literature_folder}/{p.get('publication_year') or date.today().year}"
        write_note(vault, year_folder, p["note_filename"], make_note(p))

    radar_path = write_radar(vault, radar_folder, literature_folder, discovered, date.today())
    print(f"[DONE] Wrote radar: {radar_path}")


if __name__ == "__main__":
    main()
