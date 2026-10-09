"""Local persistence, response caching, and redacted request accounting."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sqlite3
import time
from urllib.parse import urlsplit, urlunsplit

from .models import Opportunity, Problem, Source


def _identifier(kind, values):
    encoded = json.dumps(values, sort_keys=True, ensure_ascii=False).encode()
    return kind + "_" + hashlib.sha256(encoded).hexdigest()[:24]


class Store:
    """A transaction per public write; repeated saves update existing identities."""

    def __init__(self, path):
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path), timeout=30)
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY, url TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS sources_url ON sources(url);
            CREATE TABLE IF NOT EXISTS problems (
                id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id),
                payload TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS problems_source ON problems(source_id);
            CREATE TABLE IF NOT EXISTS opportunities (
                id TEXT PRIMARY KEY, payload TEXT NOT NULL,
                bookmarked INTEGER NOT NULL DEFAULT 0 CHECK(bookmarked IN (0,1)));
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY, payload TEXT NOT NULL, expires_at REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS cache_expiration ON cache(expires_at);
            CREATE TABLE IF NOT EXISTS request_logs (
                id INTEGER PRIMARY KEY, created_at REAL NOT NULL,
                provider TEXT NOT NULL, url TEXT NOT NULL, status INTEGER,
                usage TEXT, cost REAL, cached INTEGER NOT NULL CHECK(cached IN (0,1)));
            CREATE INDEX IF NOT EXISTS requests_provider ON request_logs(provider);
        """)
        columns = {row[1] for row in self.connection.execute("PRAGMA table_info(request_logs)")}
        if "phase" not in columns:
            self.connection.execute("ALTER TABLE request_logs ADD COLUMN phase TEXT NOT NULL DEFAULT 'unknown'")
        self.connection.commit()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        self.connection.close()

    def save_sources(self, sources):
        with self.connection:
            for item in sources:
                if not item.id:
                    item.id = _identifier("source", [item.url, item.content])
                self.connection.execute(
                    "INSERT INTO sources(id,url,payload) VALUES(?,?,?) "
                    "ON CONFLICT(id) DO UPDATE SET url=excluded.url,payload=excluded.payload",
                    (item.id, item.url, json.dumps(asdict(item), ensure_ascii=False)))

    def save_problems(self, problems):
        with self.connection:
            self._save_problems(problems)

    def _save_problems(self, problems):
        for item in problems:
            if not item.id:
                item.id = _identifier("problem", [item.source_id, item.statement])
            self.connection.execute(
                "INSERT INTO problems(id,source_id,payload) VALUES(?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET source_id=excluded.source_id,payload=excluded.payload",
                (item.id, item.source_id, json.dumps(asdict(item), ensure_ascii=False)))

    def replace_problems(self, source_ids, problems):
        """Atomically replace evaluations, including removing now-rejected problems."""
        source_ids = set(source_ids)
        problems = list(problems)
        if any(item.source_id not in source_ids for item in problems):
            raise ValueError("Replacement problems must belong to evaluated source IDs")
        with self.connection:
            self.connection.executemany("DELETE FROM problems WHERE source_id=?",
                                        [(id,) for id in source_ids])
            self._save_problems(problems)

    def save_opportunities(self, opportunities):
        with self.connection:
            self._save_opportunities(opportunities)

    def _save_opportunities(self, opportunities):
        for item in opportunities:
            if not item.id:
                item.id = _identifier("opportunity", [item.category, item.title])
            self.connection.execute(
                "INSERT INTO opportunities(id,payload,bookmarked) VALUES(?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                (item.id, json.dumps(asdict(item), ensure_ascii=False), int(item.bookmarked)))

    def replace_opportunities(self, opportunities):
        """Replace the corpus grouping, retaining bookmarks for continuing IDs."""
        opportunities = list(opportunities)
        with self.connection:
            self._save_opportunities(opportunities)
            current = {item.id for item in opportunities}
            stale = [(id,) for (id,) in self.connection.execute("SELECT id FROM opportunities")
                     if id not in current]
            self.connection.executemany("DELETE FROM opportunities WHERE id=?", stale)

    def load_sources(self):
        return [Source(**json.loads(row[0])) for row in self.connection.execute(
            "SELECT payload FROM sources ORDER BY id")]

    def load_problems(self):
        return [Problem(**json.loads(row[0])) for row in self.connection.execute(
            "SELECT payload FROM problems ORDER BY id")]

    def load_opportunities(self):
        result = []
        for payload, bookmarked in self.connection.execute(
                "SELECT payload,bookmarked FROM opportunities ORDER BY id"):
            data = json.loads(payload)
            data["bookmarked"] = bool(bookmarked)
            result.append(Opportunity(**data))
        return sorted(result, key=lambda item: (-item.score, item.id))

    def bookmark(self, id, value=True):
        with self.connection:
            cursor = self.connection.execute(
                "UPDATE opportunities SET bookmarked=? WHERE id=?", (int(bool(value)), id))
            if not cursor.rowcount:
                raise KeyError(f"Opportunity not found: {id}")

    def cache_get(self, key):
        row = self.connection.execute(
            "SELECT payload,expires_at FROM cache WHERE key=?", (key,)).fetchone()
        if row is None or row[1] <= time.time():
            return None
        return json.loads(row[0])

    def cache_set(self, key, value, ttl=86400):
        with self.connection:
            self.connection.execute(
                "INSERT INTO cache(key,payload,expires_at) VALUES(?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET payload=excluded.payload,expires_at=excluded.expires_at",
                (key, json.dumps(value), time.time() + ttl))

    def log_request(self, provider, url, status, usage=None, cost=None, cached=False, phase="unknown"):
        # Credentials and queries can contain keys or sensitive submitted text.
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        if parsed.port:
            host += f":{parsed.port}"
        safe_url = urlunsplit((parsed.scheme, host, parsed.path, "", ""))
        with self.connection:
            self.connection.execute(
                "INSERT INTO request_logs(created_at,provider,url,status,usage,cost,cached,phase) "
                "VALUES(?,?,?,?,?,?,?,?)", (time.time(), provider, safe_url, status,
                    json.dumps(usage) if usage is not None else None, cost, int(cached), phase))

    def usage_summary(self):
        providers = {}
        phases = {}
        for phase, count, hits, cost, priced in self.connection.execute(
                "SELECT phase,COUNT(*),SUM(cached),SUM(CASE WHEN cached=0 THEN cost ELSE 0 END),"
                "SUM(CASE WHEN cached=0 AND cost IS NOT NULL THEN 1 ELSE 0 END) FROM request_logs GROUP BY phase"):
            phases[phase] = {"requests": count, "cache_hits": hits, "network_requests": count-hits,
                             "estimated_cost": cost, "priced_requests": priced, "unpriced_requests": count-hits-priced}
        for provider, count, hits, cost, priced in self.connection.execute(
                "SELECT provider,COUNT(*),SUM(cached),SUM(CASE WHEN cached=0 THEN cost ELSE 0 END),"
                "SUM(CASE WHEN cached=0 AND cost IS NOT NULL THEN 1 ELSE 0 END) "
                "FROM request_logs GROUP BY provider"):
            providers[provider] = {"requests": count, "cache_hits": hits,
                "network_requests": count - hits, "estimated_cost": cost,
                "priced_requests": priced, "unpriced_requests": count - hits - priced,
                "usage": {}}
        for provider, payload in self.connection.execute(
                "SELECT provider,usage FROM request_logs WHERE usage IS NOT NULL AND cached=0"):
            usage = json.loads(payload)
            if isinstance(usage, dict):
                totals = providers[provider]["usage"]
                for key, value in usage.items():
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        totals[key] = totals.get(key, 0) + value
        return {"providers": providers, "phases": phases,
                "requests": sum(item["requests"] for item in providers.values()),
                "cache_hits": sum(item["cache_hits"] for item in providers.values()),
                "estimated_cost": sum(item["estimated_cost"] or 0 for item in providers.values()),
                "unpriced_requests": sum(item["unpriced_requests"] for item in providers.values()),
                "cost_note": "Costs are estimates; unpriced requests are unknown, not free."}
