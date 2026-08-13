"""Unit: LLM JSON robustness - repair for mid-JSON stops (real-run fix, no API calls)."""
from llm_client import LLMClient
from models import ResearchSubQuery


def test_repair_completes_unclosed_braces():
    # LLMs sometimes stop writing mid-JSON; completing the envelope must salvage it.
    raw = '{"thought": "x", "action": {"tool": "final", "answer": "done."}'
    assert LLMClient._repair_truncated_json(raw) == raw + "}"


def test_repair_returns_none_for_otherwise_broken_json():
    # Unterminated string cannot be repaired by adding braces.
    raw = '{"thought": "x", "action": {"tool": "final", "answer": "unterminated'
    assert LLMClient._repair_truncated_json(raw) is None


def test_subquery_id_coerced_to_str():
    # LLMs may emit numeric sub-query IDs; the contract requires strings
    # (status events, log lines, failure lists all format them as text).
    assert ResearchSubQuery(sub_query_id=2, sub_query="A").sub_query_id == "2"
