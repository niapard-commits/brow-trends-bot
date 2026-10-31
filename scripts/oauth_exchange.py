"""Одноразово: обмінює код авторизації (OAuth) на довгий токен Threads із явними дозволами
threads_basic + threads_keyword_search і зберігає його в data/token.json.
Змінні: THREADS_APP_ID, THREADS_APP_SECRET, THREADS_REDIRECT_URI, THREADS_AUTH_CODE."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect as c  # noqa: E402


def env(name: str) -> str:
    return os.environ.get(name, "").strip()


def extract_code(raw: str) -> str:
    """Приймає або сам код, або всю адресу після авторизації (…?code=AQ…#_)."""
    raw = raw.strip().split("#")[0]
    if "code=" in raw:
        raw = raw.split("code=", 1)[1].split("&")[0]
    return raw.strip()


def main() -> int:
    app_id, secret, redirect = env("THREADS_APP_ID"), env("THREADS_APP_SECRET"), env("THREADS_REDIRECT_URI")
    code = extract_code(env("THREADS_AUTH_CODE"))
    if not all([app_id, secret, redirect, code]):
        print("Бракує одного з: THREADS_APP_ID, THREADS_APP_SECRET, THREADS_REDIRECT_URI, THREADS_AUTH_CODE", file=sys.stderr)
        return 1
    print(f"Діагностика: довжина секрету {len(secret)} (очікується 32), лише літери й цифри: {secret.isalnum()}, "
          f"довжина коду {len(code)}, app_id {app_id}")
    r = requests.post(f"{c.API}/oauth/access_token", data={
        "client_id": app_id, "client_secret": secret, "grant_type": "authorization_code",
        "redirect_uri": redirect, "code": code}, timeout=30)
    if r.status_code != 200:
        print(f"Обмін коду не вдався ({r.status_code}): {r.text[:300]}", file=sys.stderr)
        return 1
    short = r.json()["access_token"]
    r = requests.get(f"{c.API}/access_token", params={
        "grant_type": "th_exchange_token", "client_secret": secret, "access_token": short}, timeout=30)
    if r.status_code != 200:
        print(f"Обмін на довгий токен не вдався ({r.status_code}): {r.text[:300]}", file=sys.stderr)
        return 1
    body = r.json()
    c.save_token({"access_token": body["access_token"],
                  "expires_at": int(time.time()) + int(body.get("expires_in", 60 * 86400))})
    me = requests.get(f"{c.API}/v1.0/me", params={"fields": "id,username", "access_token": body["access_token"]}, timeout=30)
    print("Токен збережено. Акаунт:", me.json() if me.status_code == 200 else f"/me → {me.status_code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
