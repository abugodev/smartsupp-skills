---
name: topic-clusters
description: Discover what customers talk about in Smartsupp chats — a two-level topic taxonomy built bottom-up from the conversations, every session assigned to a topic, with volume and CX per topic. Use for "topics", "what do customers ask about", "contact reasons", "drivers of chat volume", or as input for weekly pulse.
---

# Topic clusters

Builds topics from the conversations themselves (no predefined keywords), the way
Intercom's Topics Explorer does: find recurring questions, group them into
subtopics, merge subtopics into parent topics, name them, then assign every session.
The taxonomy is kept and reused so topics stay stable week to week.

**Input:** `<ws>/digest.txt` (compact view of `sessions.redacted.jsonl`; see `smartsupp-conversations` → Working efficiently); optional `<ws>/results/cx-score.jsonl`;
optional existing taxonomy from a previous run: `<ws>/../taxonomy.json` (the folder
that holds the weekly workspaces), or a path the user gives.
**Output:** `<ws>/results/topics.json`, `<ws>/results/topics.md`, updated taxonomy file.

## 1. Intents

For every session with at least one customer message, write one **intent**: what
the customer wanted, as a short canonical phrase in English, generic and without
personal data ("change a booking date", "where is my order", "price of the premium
plan"). If a session has two distinct requests, record both, the first one
primary. Greeting-only, tests, spam and misdirected messages get intent
`no request` / `misdirected` (they go to an "Other" parent).

## 2. Build the taxonomy (skip if a taxonomy exists — go to 4)

1. Group intents into **subtopics**: same underlying need, regardless of wording,
   language or which product it concerns. A subtopic should be specific enough
   to act on ("Sizing & fit", not "Products") and usually have ≥ 2 sessions.
2. Merge subtopics into **parent topics** (typically 5–12 per business line).
3. If the account serves clearly different businesses or brands (different domains,
   page paths or offerings), make the business line the first split and build
   parents within each.
4. Name topics in the language the business uses with customers; give each a one-line
   description and 2–4 example intents.

Topic ids: kebab-case, stable (`billing/refund-request`).

## 3. Quality check

- Every subtopic has a clear, distinct meaning; merge near-duplicates.
- Aim for roughly one subtopic per three to four sessions: fold a single-session subtopic into
  the subtopic whose need it shares (the same question in other words, or a narrower case of
  it — one product attribute of an attribute group, one fee of a fee list). Never merge needs a
  team would handle differently just to make a subtopic bigger; a truly distinct need may stay
  a one-session subtopic.
- No parent holds more than ~40% of sessions unless the data really is that skewed.
- "Other" holds ≤ 10% of sessions.

## 4. Assign

Assign each session to exactly one subtopic (its primary intent). With an existing
taxonomy, assign to the best fit; when ≥ 3 sessions do not fit anything, propose a
new subtopic (mark `"new": true`) instead of forcing them.

## 5. Output

`topics.json` (`secondary` is `null` or `{"topic", "intent"}`; `stats` has one row per
parent and per subtopic with `"level": "parent" | "subtopic"`, share of all sessions;
taxonomy nodes may carry `examples` and `business`):
```json
{"taxonomy": [{"id": "store/orders", "name": "…", "parent": null, "description": "…"},
              {"id": "store/orders/delivery-status", "name": "…", "parent": "store/orders", "description": "…", "new": false}],
 "assignments": {"<session_id>": {"topic": "store/orders/delivery-status", "intent": "where is my order", "secondary": null}},
 "stats": [{"topic": "…", "sessions": 12, "share": 0.08, "cx_positive_share": 0.75, "cx_mean": 4.1}]}
```

Write `taxonomy` and `assignments`, then run
`python3 ../smartsupp-conversations/scripts/insights.py topic-stats <ws>`: it fills `stats` and
prints the volume/share/CX table for topics.md.

`topics.md`: table of parent → subtopic with volume, share and CX (when available),
sorted by volume; call out high-volume / low-CX topics and new topics. No personal
data. Save the taxonomy (taxonomy + descriptions, no assignments) for the next run.
