import json
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import collect as c  # noqa: E402


class Resp:
    def __init__(self, status, body):
        self.status_code, self._b, self.text = status, body, json.dumps(body)

    def json(self):
        return self._b


def post(i, text="t", **kw):
    return {"id": i, "text": text, "username": "u" + i, "permalink": "https://threads.com/" + i,
            "timestamp": "2026-10-30T10:00:00+0000", "media_type": "TEXT_POST", **kw}


def test_collect_dedupes_and_merges_queries(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        return Resp(200, {"data": [post("1"), post("2")] if params["q"] == "a" else [post("1")]})
    monkeypatch.setattr(c.requests, "get", fake_get)
    cfg = {"queries": [{"q": "a", "lang": "uk"}, {"q": "b", "lang": "en"}], "search_types": ["TOP"], "limit": 5}
    posts, errors = c.collect("tok", cfg)
    assert set(posts) == {"1", "2"} and not errors
    assert posts["1"]["queries"] == ["a", "b"]


def test_collect_records_errors_and_continues(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        if params["q"] == "bad":
            return Resp(403, {"error": "no permission"})
        return Resp(200, {"data": [post("1")]})
    monkeypatch.setattr(c.requests, "get", fake_get)
    cfg = {"queries": [{"q": "bad", "lang": "uk"}, {"q": "ok", "lang": "uk"}], "search_types": ["TOP", "RECENT"], "limit": 5}
    posts, errors = c.collect("tok", cfg)
    assert list(posts) == ["1"] and len(errors) == 2


def test_purge_old_removes_only_expired(tmp_path):
    for name in ["2026-06-01", "2026-09-15", "notes"]:
        (tmp_path / f"{name}.json").write_text("[]")
    removed = c.purge_old(tmp_path, 90, date(2026, 10, 31))
    assert removed == ["2026-06-01.json"]
    assert (tmp_path / "2026-09-15.json").exists() and (tmp_path / "notes.json").exists()


def test_digest_truncates_and_links():
    long = "слово " * 200
    posts = {"1": {**post("1", long), "queries": ["q"]}}
    out = c.build_digest(posts, date(2026, 10, 31), ["e"])
    assert "…" in out and "https://threads.com/1" in out and "## Помилки" in out
    assert max(len(l) for l in out.splitlines()) < 450


def test_token_bootstrap_and_refresh(monkeypatch, tmp_path):
    monkeypatch.setattr(c, "TOKEN_FILE", tmp_path / "token.json")
    monkeypatch.setenv("THREADS_TOKEN", " abc\n")
    monkeypatch.setattr(c.requests, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no refresh expected")))
    assert c.ensure_token() == "abc"
    saved = json.loads((tmp_path / "token.json").read_text())
    assert saved["access_token"] == "abc"

    saved["expires_at"] = int(time.time()) + 10 * 86400
    (tmp_path / "token.json").write_text(json.dumps(saved))
    monkeypatch.setattr(c.requests, "get", lambda *a, **k: Resp(200, {"access_token": "NEW", "expires_in": 5184000}))
    assert c.ensure_token() == "NEW"
    assert json.loads((tmp_path / "token.json").read_text())["access_token"] == "NEW"


def test_refresh_failure_keeps_old_token(monkeypatch, tmp_path):
    monkeypatch.setattr(c, "TOKEN_FILE", tmp_path / "token.json")
    (tmp_path / "token.json").write_text(json.dumps({"access_token": "old", "expires_at": int(time.time()) + 86400}))
    monkeypatch.setattr(c.requests, "get", lambda *a, **k: Resp(400, {"error": "x"}))
    assert c.ensure_token() == "old"
