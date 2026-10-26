#!/usr/bin/env python3
"""Turn raw Smartsupp MCP conversation dumps into session-level transcripts.

Input: a directory of JSON files, one per conversation, each the result of the
Smartsupp MCP `get_conversation` tool (messages included). Optionally a
`contacts/` subdirectory with `get_contact` results named <contact_id>.json.

Output: JSON Lines, one record per *session*. Smartsupp keeps one conversation per
visitor and reopens it on every new chat, so a conversation is split into sessions
at each `chat_close` event. Each session record:

  {
    "session_id": "<conversation_id>#<n>",
    "conversation_id", "session_index", "started_at", "closed_at", "close_type",
    "status": "closed" | "open",
    "channel", "domain", "pages": [paths the customer wrote from],
    "contact_id", "tags": [tag ids], "rating": {"value", "text"} | null,
    "initiated_by": "customer" | "business",
    "messages": [{"at", "role", "text", "author"}],   # roles: customer, operator, ai_agent, bot, system
    "events": [{"at", "type", "data"}],
    "stats": {"customer_messages", "operator_messages", "ai_messages",
              "first_reply_role", "handover", "handover_after_ai_messages"}
  }

Usage: normalize.py <raw_dir> <out.jsonl> [--keep-vars] [--ai-trigger TRIGGER_ID]...
Conversation variables are dropped unless --keep-vars is given (they may carry
integration data that is not part of the conversation).
Standard library only.
"""
import json
import os
import sys
from urllib.parse import urlparse

# Smartsupp message.sub_type -> transcript role.
ROLE = {"contact": "customer", "agent": "operator", "bot": "bot", "system": "system"}


AI_TRIGGERS = set()  # extra AI-agent trigger ids, from --ai-trigger


def role_of(msg):
    st = msg.get("sub_type")
    tid = msg.get("trigger_id") or ""
    if st == "bot" or tid:
        # Smartsupp AI agents post as sub_type "bot" with trigger_id = the AI
        # chatbot workflow id, which starts with "bo" (…/ai-chatbots/workflow/boXXXX).
        # Other triggers are rule-based automations.
        if tid.startswith("bo") or tid in AI_TRIGGERS:
            return "ai_agent"
        return "bot"
    return ROLE.get(st, st or "other")


def text_of(msg):
    c = msg.get("content") or {}
    if c.get("text"):
        return c["text"].strip()
    return None


def page_path(url):
    if not url:
        return None
    p = urlparse(url)
    return p.path or "/"


def split_sessions(conv):
    items = sorted((conv.get("messages") or {}).get("items", []), key=lambda m: m["created_at"])
    sessions, cur = [], []
    for m in items:
        cur.append(m)
        c = m.get("content") or {}
        if m.get("type") == "event" and c.get("type") == "chat_close":
            sessions.append(cur)
            cur = []
    # Trailing items after the last close: a rating form belongs to the closed session;
    # anything else starts an open session.
    trailing_ratings = [m for m in cur if (m.get("content") or {}).get("type") == "rate_form"]
    rest = [m for m in cur if m not in trailing_ratings]
    if trailing_ratings and sessions:
        sessions[-1].extend(trailing_ratings)
    if rest:
        sessions.append(rest)
    return sessions


def build_session(conv, idx, items, keep_vars):
    messages, events, pages = [], [], []
    rating, close_type, closed_at = None, None, None
    for m in items:
        c = m.get("content") or {}
        if m.get("type") == "message" and c.get("type") == "rate_form":
            d = c.get("data") or {}
            rating = {"value": d.get("value"), "text": d.get("text")}
            continue
        if m.get("type") == "event":
            events.append({"at": m["created_at"], "type": c.get("type"), "data": c.get("data")})
            if c.get("type") == "chat_close":
                close_type = (c.get("data") or {}).get("close_type")
                closed_at = m["created_at"]
            continue
        txt = text_of(m)
        if txt is None and not m.get("attachments"):
            continue
        role = role_of(m)
        if role == "customer":
            p = page_path(m.get("page_url"))
            if p and p not in pages:
                pages.append(p)
        messages.append({
            "at": m["created_at"],
            "role": role,
            "text": txt or "[attachment]",
            "author": m.get("agent_id") or m.get("trigger_name") or None,
        })

    roles = [x["role"] for x in messages]
    replies = [r for r in roles if r in ("operator", "ai_agent", "bot")]
    first_ai = next((i for i, r in enumerate(roles) if r == "ai_agent"), None)
    first_op = next((i for i, r in enumerate(roles) if r == "operator"), None)
    handover = first_ai is not None and first_op is not None and first_op > first_ai
    stats = {
        "customer_messages": roles.count("customer"),
        "operator_messages": roles.count("operator"),
        "ai_messages": roles.count("ai_agent"),
        "first_reply_role": replies[0] if replies else None,
        "handover": handover,
        "handover_after_ai_messages": roles[:first_op].count("ai_agent") if handover else None,
    }
    rec = {
        "session_id": f"{conv['id']}#{idx}",
        "conversation_id": conv["id"],
        "session_index": idx,
        "started_at": items[0]["created_at"] if items else conv.get("created_at"),
        "closed_at": closed_at,
        "close_type": close_type,
        "status": "closed" if closed_at else "open",
        "channel": (conv.get("channel") or {}).get("type"),
        "domain": conv.get("domain"),
        "pages": pages,
        "contact_id": conv.get("contact_id"),
        "tags": [t["id"] for t in (conv.get("tags") or {}).get("data", [])],
        "rating": rating,
        "initiated_by": "customer" if roles and roles[0] == "customer" else "business",
        "messages": messages,
        "events": events,
        "stats": stats,
    }
    if keep_vars:
        rec["variables"] = conv.get("variables") or {}
    return rec


def main():
    argv = sys.argv[1:]
    while "--ai-trigger" in argv:
        i = argv.index("--ai-trigger")
        AI_TRIGGERS.add(argv[i + 1])
        del argv[i:i + 2]
    args = [a for a in argv if not a.startswith("--")]
    keep_vars = "--keep-vars" in argv
    raw_dir, out_path = args
    n_conv = n_sess = 0
    with open(out_path, "w", encoding="utf-8") as out:
        for fn in sorted(os.listdir(raw_dir)):
            if not fn.endswith(".json"):
                continue
            conv = json.load(open(os.path.join(raw_dir, fn), encoding="utf-8"))
            n_conv += 1
            parts = split_sessions(conv)
            for i, items in enumerate(parts):
                rec = build_session(conv, i, items, keep_vars)
                # Conversations closed via API/auto-close may lack a chat_close event:
                # the last session then takes the conversation's own close.
                if i == len(parts) - 1 and rec["status"] == "open" and conv.get("status") == "closed":
                    rec["status"] = "closed"
                    rec["closed_at"] = conv.get("finished_at")
                    rec["close_type"] = rec["close_type"] or "conversation_closed"
                if rec["messages"]:
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    n_sess += 1
    print(f"{n_conv} conversations -> {n_sess} sessions -> {out_path}")


if __name__ == "__main__":
    main()
