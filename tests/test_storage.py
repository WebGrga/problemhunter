import sqlite3

import pytest

from problem_hunter.models import Opportunity, Problem, Source
from problem_hunter.storage import Store


def test_roundtrip_upserts_preserve_bookmark(tmp_path):
    path = tmp_path / "data.sqlite"
    source = Source("https://example.org/post", "Complaint", "Manual appointments waste hours")
    with Store(path) as store:
        store.save_sources([source, source])
        problem = Problem(source.id, "Manual appointment entry", "restaurants")
        store.save_problems([problem, problem])
        opportunity = Opportunity("appointments", "Appointments", "Manual entry", "restaurants",
                                  problem_ids=[problem.id], source_ids=[source.id])
        store.save_opportunities([opportunity])
        store.bookmark(opportunity.id)
        opportunity.score = 50
        store.save_opportunities([opportunity, opportunity])
    with Store(path) as store:
        assert store.load_sources() == [source]
        assert store.load_problems() == [problem]
        loaded = store.load_opportunities()
        assert len(loaded) == 1
        assert loaded[0].bookmarked
        assert loaded[0].score == 50
        store.bookmark(opportunity.id, False)
        assert not store.load_opportunities()[0].bookmarked


def test_stable_empty_identifiers(tmp_path):
    with Store(tmp_path / "data.sqlite") as store:
        first = Source("https://example.org", "First title", "same content")
        second = Source("https://example.org", "Updated title", "same content")
        store.save_sources([first, second])
        assert first.id == second.id
        assert len(store.load_sources()) == 1
        assert store.load_sources()[0].title == "Updated title"


def test_cache_expiry_and_request_redaction(tmp_path):
    with Store(tmp_path / "data.sqlite") as store:
        response = {"status": 200, "headers": {}, "body": {"result": "cached"}}
        store.cache_set("live", response)
        store.cache_set("expired", response, ttl=-1)
        assert store.cache_get("live") == response
        assert store.cache_get("expired") is None
        assert store.cache_get("missing") is None
        store.log_request("brave", "https://user:secret@example.org/search?token=secret#secret", 200,
                          usage={"requests": 1}, cost=0.005)
        store.log_request("brave", "https://example.org/search", 200, cached=True)
        store.log_request("jev", "https://example.org/judge", 503)
        logged_url = store.connection.execute("SELECT url FROM request_logs LIMIT 1").fetchone()[0]
        assert logged_url == "https://example.org/search"
        summary = store.usage_summary()
        assert summary["requests"] == 3
        assert summary["cache_hits"] == 1
        assert summary["estimated_cost"] == pytest.approx(0.005)
        assert summary["unpriced_requests"] == 1
        assert summary["providers"]["brave"]["usage"] == {"requests": 1}


def test_missing_bookmark_and_missing_source_fail(tmp_path):
    with Store(tmp_path / "data.sqlite") as store:
        with pytest.raises(KeyError):
            store.bookmark("missing")
        with pytest.raises(sqlite3.IntegrityError):
            store.save_problems([Problem("missing", "Problem", "category")])


def test_replacement_clears_rejected_and_retains_other_sources(tmp_path):
    with Store(tmp_path / "data.sqlite") as store:
        store.save_sources([Source("https://a.org", "A", "A", id="a"),
                            Source("https://b.org", "B", "B", id="b")])
        store.save_problems([Problem("a", "Old A", "x", id="old-a"),
                             Problem("b", "Old B", "x", id="old-b")])
        store.replace_problems(["a"], [Problem("a", "New A", "x", id="new-a")])
        assert {p.id for p in store.load_problems()} == {"new-a", "old-b"}
        store.replace_problems(["a"], [])
        assert {p.id for p in store.load_problems()} == {"old-b"}
        # An insertion failure rolls back removals in the same transaction.
        with pytest.raises(sqlite3.IntegrityError):
            store.replace_problems(["b", "missing"], [Problem("missing", "New", "x")])
        assert {p.id for p in store.load_problems()} == {"old-b"}


def test_replace_opportunities_prunes_stale_preserves_continuing_bookmark(tmp_path):
    with Store(tmp_path / "data.sqlite") as store:
        first = Opportunity("first", "First", "First", "x")
        stale = Opportunity("stale", "Stale", "Stale", "x")
        store.save_opportunities([first, stale])
        store.bookmark("first")
        store.replace_opportunities([Opportunity("first", "Updated", "First", "x")])
        assert len(store.load_opportunities()) == 1
        assert store.load_opportunities()[0].bookmarked
        assert store.load_opportunities()[0].title == "Updated"
        store.replace_opportunities([])
        assert store.load_opportunities() == []

