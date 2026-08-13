"""Unit: flat-dependency detection (FR-002, T015)."""
import pytest
from models import ResearchSubQuery, validate_flat, DependencyError


def test_flat_subqueries_pass():
    subs = [ResearchSubQuery("s1", "query A"), ResearchSubQuery("s2", "query B")]
    validate_flat(subs)  # no raise


def test_dependent_subqueries_rejected():
    subs = [ResearchSubQuery("s1", "A"), ResearchSubQuery("s2", "B", depends_on=["s1"])]
    with pytest.raises(DependencyError):
        validate_flat(subs)


def test_empty_subquery_rejected():
    subs = [ResearchSubQuery("s1", "   ")]
    with pytest.raises(ValueError):
        validate_flat(subs)
