# automated-lit-review-tool
a local literature-monitoring tool for an academic research workflow

It does four things:

1. Finds new papers from journals listed in `config/journals.yaml` using OpenAlex.
2. Deduplicates papers and stores raw metadata in `data/papers.jsonl`.
3. Scores each paper against `config/research_profile.yaml` using Claude.
4. Writes a ranked Markdown radar report and individual paper notes into an Obsidian vault.

The first version is intentionally simple: Python + OpenAlex + Claude API + Obsidian Markdown files. It does not require an Obsidian plugin. An optional Obsidian Local REST API mode is included later.

## Setup

Create a virtual environment and install. Then edit `.env` and supply both `OPENALEX_API_KEY` and `ANTHROPIC_API_KEY` plus your Obsidian vault path:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add the Claude API key and your Obsidian vault path.

Then run:

```bash
python3 -m src.radar --from 2018-12-01 --to 2018-12-31
```

For a dry run:

```bash
python3 -m src.radar --from 2018-12-01 --to 2018-12-31 --dry-run
```

For a daily run, schedule the same command with cron, launchd, Windows Task Scheduler, or another local scheduler.

## Architecture

OpenAlex is used for journal-level discovery. The current OpenAlex API requires an API key, which you can obtain from the OpenAlex settings page. because its Works API supports publication-date filters and source/journal filtering. It also exposes abstracts, DOI, open-access information, and related metadata.

Claude is used only after candidate papers are collected. This keeps the expensive language-model step focused on relevance judgment instead of using an LLM as the initial search engine.

The research profile separates topics, phenomena, theories/mechanisms, methods, contexts, active projects, and explicit exclusions. This is important because two papers can be textually similar while being strategically irrelevant to a research agenda.

## Output

The tool creates:

```text
Literature Radar/
  2026-08-16.md

Literature/
  2026/
    Paper Title.md
```

The radar report ranks papers by:

- Overall relevance
- Topic relevance
- Theory/mechanism relevance
- Phenomenon relevance
- Method relevance
- Context/data relevance
- Novelty/research-potential relevance

It also asks Claude to explain why a paper matters to the user's active projects and what, if anything, may be borrowed from it.

## Important limitation

OpenAlex primarily gives bibliographic metadata and abstract-level text through its API. A paper's full text is not automatically retrieved when it is paywalled. The current version therefore performs relevance scoring from metadata and abstract. For open-access papers, a later extension can add full-text analysis.
