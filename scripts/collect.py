"""Тижневий збирач публічних дописів Threads за ключовими словами (Threads API, keyword_search).
Нічого не публікує. Зберігає: текст, ім'я користувача, посилання, час, тип медіа.
Сирі файли старші за retention_days видаляються (політика конфіденційності: 90 днів).

Змінні: THREADS_TOKEN (початковий довгий токен, потрібен лише поки немає data/token.json).
Використання: python scripts/collect.py [--dry-run]"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
API = "https://graph.threads.net"
KEYWORDS = ROOT / "keywords.json"
TOKEN_FILE = ROOT / "data/token.json"
RAW_DIR = ROOT / "data/raw"
DIGEST_FILE = ROOT / "data/digest-input.md"
FIELDS = "id,text,media_type,permalink,timestamp,username,has_replies,is_quote_post,is_reply"
REFRESH_BEFORE = 30 * 86400
FALLBACK_TTL = 55 * 86400
EXCERPT = 280  # у дайджест потрапляє лише короткий уривок (політика)


# ---------- токен ----------

def load_token() -> dict | None:
    try:
        return json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save_token(data: dict) -> None:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps(data, indent=1), encoding="utf-8")


def ensure_token() -> str:
    """Повертає робочий токен: бере з файлу, інакше з THREADS_TOKEN; оновлює, коли лишилось <30 днів."""
    tok = load_token()
    if not tok:
        raw = os.environ.get("THREADS_TOKEN", "").strip()
        if not raw:
            raise SystemExit("Немає токена: ні data/token.json, ні секрету THREADS_TOKEN.")
        tok = {"access_token": raw, "expires_at": int(time.time()) + FALLBACK_TTL}
        save_token(tok)
    if tok["expires_at"] - time.time() < REFRESH_BEFORE:
        r = requests.get(f"{API}/refresh_access_token", params={
            "grant_type": "th_refresh_token", "access_token": tok["access_token"]}, timeout=30)
        if r.status_code == 200:
            body = r.json()
            tok = {"access_token": body["access_token"],
                   "expires_at": int(time.time()) + int(body.get("expires_in", 60 * 86400))}
            save_token(tok)
        else:
            print(f"Оновлення токена не вдалось ({r.status_code}): {r.text[:200]}", file=sys.stderr)
    return tok["access_token"]


# ---------- пошук ----------

def search(token: str, q: str, search_type: str, limit: int) -> list[dict]:
    r = requests.get(f"{API}/keyword_search", params={
        "q": q, "search_type": search_type, "search_mode": "KEYWORD",
        "limit": limit, "fields": FIELDS, "access_token": token}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code}: {r.text[:300]}")
    return r.json().get("data", [])


def collect(token: str, cfg: dict) -> tuple[dict[str, dict], list[str]]:
    posts: dict[str, dict] = {}
    errors: list[str] = []
    for item in cfg["queries"]:
        for st in cfg["search_types"]:
            try:
                rows = search(token, item["q"], st, cfg["limit"])
            except (RuntimeError, requests.RequestException) as e:
                errors.append(f"«{item['q']}» {st}: {e}")
                continue
            for p in rows:
                cur = posts.setdefault(p["id"], {
                    "id": p["id"], "text": p.get("text", ""), "username": p.get("username", ""),
                    "permalink": p.get("permalink", ""), "timestamp": p.get("timestamp", ""),
                    "media_type": p.get("media_type", ""), "has_replies": p.get("has_replies", False),
                    "is_reply": p.get("is_reply", False), "queries": [], "lang": item["lang"]})
                if item["q"] not in cur["queries"]:
                    cur["queries"].append(item["q"])
    return posts, errors


# ---------- зберігання і ретеншн ----------

def purge_old(raw_dir: Path, days: int, today: date) -> list[str]:
    removed = []
    cutoff = today - timedelta(days=days)
    for f in raw_dir.glob("*.json"):
        try:
            d = date.fromisoformat(f.stem)
        except ValueError:
            continue
        if d < cutoff:
            f.unlink()
            removed.append(f.name)
    return removed


def excerpt(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= EXCERPT else text[:EXCERPT].rstrip() + "…"


def build_digest(posts: dict[str, dict], today: date, errors: list[str]) -> str:
    """Короткий текстовий вхід для тижневого дайджесту: уривки + посилання, згруповано за запитом."""
    lines = [f"# Threads: збір за {today.isoformat()}", f"Дописів: {len(posts)}", ""]
    by_q: dict[str, list[dict]] = {}
    for p in posts.values():
        for q in p["queries"]:
            by_q.setdefault(q, []).append(p)
    for q, rows in sorted(by_q.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"## {q} ({len(rows)})")
        for p in sorted(rows, key=lambda x: x["timestamp"], reverse=True)[:8]:
            lines.append(f"- @{p['username']} [{p['media_type']}] {excerpt(p['text'])} {p['permalink']}")
        lines.append("")
    if errors:
        lines += ["## Помилки", *[f"- {e}" for e in errors]]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="не писати файли")
    args = ap.parse_args()
    cfg = json.loads(KEYWORDS.read_text(encoding="utf-8"))
    token = ensure_token()
    posts, errors = collect(token, cfg)
    today = datetime.now(timezone.utc).date()
    digest = build_digest(posts, today, errors)
    if args.dry_run:
        print(digest)
        return 0
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / f"{today.isoformat()}.json").write_text(
        json.dumps(list(posts.values()), ensure_ascii=False, indent=1), encoding="utf-8")
    DIGEST_FILE.write_text(digest, encoding="utf-8")
    removed = purge_old(RAW_DIR, cfg["retention_days"], today)
    print(f"Зібрано {len(posts)} дописів, помилок {len(errors)}, видалено старих файлів {len(removed)}.")
    for e in errors[:5]:
        print("Помилка:", e, file=sys.stderr)
    if errors and not posts:
        return 1  # усе впало, наприклад, бракує схвалення keyword_search
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
