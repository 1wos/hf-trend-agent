"""Hugging Face Hub API tools for the HF Trend Agent.

This module provides tool functions that query the Hugging Face Hub
public REST API for trending models, datasets, and model details.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

HF_API_BASE = "https://huggingface.co/api"
REQUEST_TIMEOUT_SECONDS = 10
DEFAULT_LIMIT = 5
MAX_LIMIT = 10
MAX_TAGS_DISPLAY = 10

VALID_TASKS: frozenset[str] = frozenset({
    "text-generation",
    "text-to-image",
    "image-classification",
    "automatic-speech-recognition",
    "translation",
    "summarization",
    "question-answering",
    "fill-mask",
    "sentence-similarity",
    "object-detection",
    "text-classification",
    "image-to-text",
    "feature-extraction",
    "image-text-to-text",
})

_session = requests.Session()
_hf_token = os.environ.get("HF_TOKEN", "")
_headers: dict[str, str] = {
    "Accept": "application/json",
    "User-Agent": "HF-Trend-Agent/1.0 (Google Cloud Run; ADK)",
}
if _hf_token:
    _headers["Authorization"] = f"Bearer {_hf_token}"
_session.headers.update(_headers)


def _clamp_limit(limit: int) -> int:
    """Clamp *limit* to the allowed range [1, MAX_LIMIT]."""
    return max(1, min(limit, MAX_LIMIT))


def _make_request(endpoint: str, params: dict[str, Any] | None = None) -> Any:
    """Send a GET request to the HF API and return parsed JSON with retry."""
    url = f"{HF_API_BASE}/{endpoint.lstrip('/')}"
    for attempt in range(5):
        response = _session.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        if response.status_code == 429:
            wait = 3 * (attempt + 1)
            logger.warning("HF API rate limited (attempt %d), retrying in %ds...", attempt + 1, wait)
            time.sleep(wait)
            continue
        response.raise_for_status()
        return response.json()
    response.raise_for_status()
    return response.json()


def _error_response(action: str, exc: Exception) -> dict[str, str]:
    """Build a standardised error payload and log the exception."""
    logger.exception("HF API error during %s", action)
    return {"status": "error", "message": f"Failed to {action}: {type(exc).__name__}"}


# ── ADK Tool Functions ──────────────────────────────────────────────


def get_trending_models(task: str = "", limit: int = DEFAULT_LIMIT) -> dict:
    """Fetch trending models from the Hugging Face Hub.

    Args:
        task: Optional pipeline-tag filter (e.g. 'text-generation',
              'image-classification', 'automatic-speech-recognition').
              Leave empty to get overall trending models.
        limit: Number of models to return (1-10, default 5).

    Returns:
        A dict with status, filter_task, count, and models list.
    """
    try:
        limit = _clamp_limit(limit)
        params: dict[str, Any] = {
            "sort": "trendingScore",
            "limit": limit,
        }

        cleaned_task = task.strip() if task else ""
        if cleaned_task and cleaned_task in VALID_TASKS:
            params["pipeline_tag"] = cleaned_task

        raw_models = _make_request("models", params)

        models = [
            {
                "id": m.get("id", "N/A"),
                "pipeline_tag": m.get("pipeline_tag", "N/A"),
                "likes": m.get("likes", 0),
                "downloads": m.get("downloads", 0),
                "trending_score": m.get("trendingScore", 0),
                "last_modified": m.get("lastModified", "N/A"),
            }
            for m in raw_models
        ]

        return {
            "status": "success",
            "filter_task": cleaned_task or "all",
            "count": len(models),
            "models": models,
        }
    except requests.RequestException as exc:
        return _error_response("fetch trending models", exc)


def get_trending_datasets(limit: int = DEFAULT_LIMIT) -> dict:
    """Fetch trending datasets from the Hugging Face Hub.

    Args:
        limit: Number of datasets to return (1-10, default 5).

    Returns:
        A dict with status, count, and datasets list.
    """
    try:
        limit = _clamp_limit(limit)
        params: dict[str, Any] = {
            "sort": "trendingScore",
            "limit": limit,
        }

        raw_datasets = _make_request("datasets", params)

        datasets = [
            {
                "id": ds.get("id", "N/A"),
                "likes": ds.get("likes", 0),
                "downloads": ds.get("downloads", 0),
                "trending_score": ds.get("trendingScore", 0),
                "last_modified": ds.get("lastModified", "N/A"),
                "tags": ds.get("tags", [])[:MAX_TAGS_DISPLAY],
            }
            for ds in raw_datasets
        ]

        return {
            "status": "success",
            "count": len(datasets),
            "datasets": datasets,
        }
    except requests.RequestException as exc:
        return _error_response("fetch trending datasets", exc)


def search_models(query: str = "", task: str = "", sort_by: str = "trendingScore", limit: int = DEFAULT_LIMIT) -> dict:
    """Search models on the Hugging Face Hub by keyword.

    Args:
        query: Search keyword (e.g. 'exaone', 'whisper', 'llama', 'korean').
        task: Optional pipeline-tag filter (e.g. 'text-generation').
        sort_by: Sort results by 'trendingScore', 'downloads', 'likes', or 'lastModified'.
            Default is 'trendingScore'.
        limit: Number of models to return (1-10, default 5).

    Returns:
        A dict with status, query, count, and models list.
    """
    if not query or not query.strip():
        return {"status": "error", "message": "query must not be empty."}

    try:
        limit = _clamp_limit(limit)
        valid_sorts = {"trendingScore", "downloads", "likes", "lastModified"}
        sort_by = sort_by if sort_by in valid_sorts else "trendingScore"

        params: dict[str, Any] = {
            "search": query.strip(),
            "sort": sort_by,
            "limit": limit,
        }

        cleaned_task = task.strip() if task else ""
        if cleaned_task and cleaned_task in VALID_TASKS:
            params["pipeline_tag"] = cleaned_task

        raw_models = _make_request("models", params)

        models = [
            {
                "id": m.get("id", "N/A"),
                "author": m.get("author", "N/A"),
                "pipeline_tag": m.get("pipeline_tag", "N/A"),
                "likes": m.get("likes", 0),
                "downloads": m.get("downloads", 0),
                "trending_score": m.get("trendingScore", 0),
                "last_modified": m.get("lastModified", "N/A"),
            }
            for m in raw_models
        ]

        return {
            "status": "success",
            "query": query.strip(),
            "filter_task": cleaned_task or "all",
            "sort_by": sort_by,
            "count": len(models),
            "models": models,
        }
    except requests.RequestException as exc:
        return _error_response(f"search models for '{query}'", exc)


def get_model_info(model_name: str = "") -> dict:
    """Fetch detailed information about a specific Hugging Face model.

    Args:
        model_name: The model identifier
            (e.g. 'meta-llama/Llama-3-8B', 'openai/whisper-large-v3').

    Returns:
        A dict with status and nested model details.
    """
    if not model_name or not model_name.strip():
        return {"status": "error", "message": "model_name must not be empty."}

    model_name = model_name.strip()

    try:
        raw = _make_request(f"models/{model_name}")

        return {
            "status": "success",
            "model": {
                "id": raw.get("id", "N/A"),
                "author": raw.get("author", "N/A"),
                "pipeline_tag": raw.get("pipeline_tag", "N/A"),
                "library_name": raw.get("library_name", "N/A"),
                "likes": raw.get("likes", 0),
                "downloads": raw.get("downloads", 0),
                "tags": raw.get("tags", [])[:MAX_TAGS_DISPLAY],
                "created_at": raw.get("createdAt", "N/A"),
                "last_modified": raw.get("lastModified", "N/A"),
            },
        }
    except requests.RequestException as exc:
        return _error_response(f"fetch model info for '{model_name}'", exc)
