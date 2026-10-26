#!/usr/bin/env python3
"""Write a compact, readable digest of the redacted sessions for the analysis skills.

    digest.py <ws>            -> <ws>/digest.txt  (and prints its size)

One block per session: a header line with what the skills need to know about the
session, then one line per message — role letter, seconds since the first message,
text. Roles: C customer, A AI agent / bot, O human operator. About half the size of
sessions.redacted.jsonl; read it once instead of writing your own dump script.

    === <session_id> | <started> | <status> | by <initiated_by> | <handled_by> | handover <y/n> | rating <n|-> | page <first page|-> | domain <domain|->
    C 0: …
    A 4: …
    O 52: …
"""
import json
import os
import sys
from datetime import datetime

ROLE = {"customer": "C", "ai_agent": "A", "bot": "A", "operator": "O"}


def handled_by(s):
    st = s.get("stats") or {}
    ai, op = st.get("ai_messages", 0) > 0, st.get("operator_messages", 0) > 0
    return {(True, True): "ai_and_operator", (True, False): "ai_only",
            (False, True): "operator_only", (False, False): "none"}[(ai, op)]


def ts(x):
    return datetime.fromisoformat(x.replace("Z", "+00:00"))


def block(s):
    rating = (s.get("rating") or {}).get("value")
    page = (s.get("pages") or ["-"])[0]
    head = (f"=== {s['session_id']} | {s.get('started_at', '')[:16].replace('T', ' ')} | {s.get('status')} | "
            f"by {s.get('initiated_by')} | {handled_by(s)} | handover {'y' if (s.get('stats') or {}).get('handover') else 'n'} | "
            f"rating {rating if rating is not None else '-'} | page {page} | domain {s.get('domain') or '-'}")
    lines = [head]
    msgs = [m for m in s.get("messages", []) if m.get("text")]
    t0 = ts(msgs[0]["at"]) if msgs else None
    for m in msgs:
        sec = int((ts(m["at"]) - t0).total_seconds()) if t0 else 0
        text = " ".join(m["text"].split())
        lines.append(f"{ROLE.get(m['role'], '?')} {sec}: {text}")
    if s.get("rating") and s["rating"].get("text"):
        lines.append(f"R: {' '.join(s['rating']['text'].split())}")
    return "\n".join(lines)


def main():
    ws = sys.argv[1]
    src = os.path.join(ws, "sessions.redacted.jsonl")
    sessions = [json.loads(l) for l in open(src, encoding="utf-8")]
    out = os.path.join(ws, "digest.txt")
    text = "\n\n".join(block(s) for s in sessions) + "\n"
    open(out, "w", encoding="utf-8").write(text)
    print(f"{out}: {len(sessions)} sessions, {len(text)} chars (sessions.redacted.jsonl: {os.path.getsize(src)} bytes)")


if __name__ == "__main__":
    main()
