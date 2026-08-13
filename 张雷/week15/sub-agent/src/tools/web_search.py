"""web_search tool (Constitution Art. 2.1: usable by main agent + subagents).

Contract (contracts/tools.md):
  input  : {query: str, **opts}
  output : {results: list[{title,url,snippet}], error: str | None}
  guarantee: NEVER raises - backend failures become {results: [], error}.
"""
from typing import Callable, Optional


def default_backend(query: str, **opts) -> list:
    """Default backend returns empty results. Plug a real search API in production."""
    return []


def web_search(query: str, backend: Optional[Callable] = None, **opts) -> dict:
    if backend is None:
        backend = default_backend
    try:
        results = backend(query, **opts)
        return {"results": results, "error": None}
    except Exception as e:  # contract: never raises
        return {"results": [], "error": str(e)}
