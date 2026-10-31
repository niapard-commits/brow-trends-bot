import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import collect as c  # noqa: E402
import oauth_exchange as o  # noqa: E402


class Resp:
    def __init__(self, status, body):
        self.status_code, self._b, self.text = status, body, json.dumps(body)

    def json(self):
        return self._b


def _env(monkeypatch, tmp_path, code=" CODE#_\n"):
    monkeypatch.setattr(c, "TOKEN_FILE", tmp_path / "token.json")
    for k, v in {"THREADS_APP_ID": "1", "THREADS_APP_SECRET": " s\n", "THREADS_REDIRECT_URI": "https://x/", "THREADS_AUTH_CODE": code}.items():
        monkeypatch.setenv(k, v)


def test_exchange_chain_saves_long_token(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    seen = {}

    def post(url, data=None, timeout=None):
        seen.update(data)
        return Resp(200, {"access_token": "SHORT"})

    def get(url, params=None, timeout=None):
        if url.endswith("/access_token"):
            return Resp(200, {"access_token": "LONG", "expires_in": 5184000})
        return Resp(200, {"id": "7", "username": "u"})

    monkeypatch.setattr(o.requests, "post", post)
    monkeypatch.setattr(o.requests, "get", get)
    assert o.main() == 0
    assert seen["code"] == "CODE" and seen["client_secret"] == "s"
    assert json.loads((tmp_path / "token.json").read_text())["access_token"] == "LONG"


def test_failed_code_exchange_saves_nothing(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    monkeypatch.setattr(o.requests, "post", lambda *a, **k: Resp(400, {"error": "bad code"}))
    assert o.main() == 1
    assert not (tmp_path / "token.json").exists()


def test_missing_env_fails(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path, code="")
    assert o.main() == 1
