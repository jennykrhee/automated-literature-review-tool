from __future__ import annotations

from datetime import date
from typing import Any

import requests

OPENALEX_URL = "https://api.openalex.org/"


def find_source(
    journal: str,
    email: str = "",
    api_key: str = "",
) -> dict[str, Any] | None:
    params = {"search": journal, "per-page": 5}

    if api_key:
        params["api_key"] = api_key

    if email:
        params["mailto"] = email

    r = requests.get(
        OPENALEX_URL + "sources",
        params=params,
        timeout=30,
    )
    r.raise_for_status()

    results = r.json().get("results", [])

    if not results:
        return None

    journal_lower = journal.lower()
    exact = [
        x
        for x in results
        if str(x.get("display_name", "")).lower() == journal_lower
    ]

    candidates = exact or results
    return candidates[0]


def fetch_recent_works(
    source_id: str,
    start_date: date,
    end_date: date,
    email: str = "",
    api_key: str = "",
) -> list[dict[str, Any]]:

    params = {
        "filter": (
            f"primary_location.source.id:{source_id},"
            f"from_publication_date:{start_date.isoformat()},"
            f"to_publication_date:{end_date.isoformat()},"
            f"type:article"
        ),
        "sort": "publication_date:desc",
        "per_page": 100,
        "select": (
            "id,doi,title,display_name,publication_date,publication_year,"
            "type,abstract_inverted_index,authorships,primary_location,"
            "open_access,cited_by_count,topics,concepts,ids"
        ),
    }

    if email:
        params["mailto"] = email

    if api_key:
        params["api_key"] = api_key

    r = requests.get(
        OPENALEX_URL + "works",
        params=params,
        timeout=60,
    )
    r.raise_for_status()

    return r.json().get("results", [])