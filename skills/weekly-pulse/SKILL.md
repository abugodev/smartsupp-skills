---
name: weekly-pulse
description: Weekly customer-voice digest from Smartsupp chats — volume, CX score, top and rising topics, what drives bad experiences, new knowledge gaps, feature requests and product info gaps — as a short Slack-ready post. Use for "weekly pulse", "weekly report of chats", "voice of customer digest", "summary for the team", or scheduled weekly runs.
---

# Weekly pulse

**Input:** a workspace for the week (`smartsupp-insights/<YYYY-Www>/`) with the results
of the other skills. Run what is missing, in this order: `smartsupp-conversations` →
`cx-score` → `topic-clusters` → `knowledge-gaps` → `contradiction-finder` →
`feedback-drafts` → `product-info-gaps`. If the previous week's workspace exists, use
it for comparisons. Also `get_statistics` (metrics `new_conversation`,
`closed_conversation`, `first_response_time`, `conversation_ratings`) for the same
dates. These official statistics count **only conversations a human operator handled**
(AI-only chats are missing: on the test account on 2026-10-10, `new_conversation` was 129
while the transcripts held 220 conversations), so:
take total volume and the AI only / AI + human / human only split from the sessions;
report the official numbers as "operator-handled chats", "human first response" and
"operator rating" — never as totals for all chats. If `get_statistics` is unavailable,
compute first response from transcripts and say so.
**Output:** `<ws>/results/weekly-pulse.md` (the post) and `<ws>/results/weekly-pulse.json`.

Take every number (volume, handled-by split, first response, CX, top topics with ties, top
gaps, feature requests, product info gap, contradictions) from
`python3 ../smartsupp-conversations/scripts/insights.py pulse-metrics <ws>` — do not recount.

## Content (in this order, ≤ 2 500 characters total)

1. **Headline numbers:** chats, CX score % (vs. last week), share handled by AI only /
   AI + human / human only, median first response time.
2. **Top topics:** 5 largest **parent topics** (not subtopics; leave out "Other") by volume with share and CX; mark ▲/▼ movers vs. last
   week (≥ 30% change and ≥ 3 sessions).
3. **What hurt:** the 3 biggest drivers of low CX (topic + reason), one line each.
4. **Fix next:** top 3 knowledge gaps (by count), any contradiction found, top product
   info gap — each with the one action to take.
5. **Customers asked for:** top 3 feature requests with counts.
6. Link or path to the full results.

Plain language, no jargon, numbers rounded. No personal data and no individual
operator performance. Apply the personal-data gate and run `python3 ../smartsupp-conversations/scripts/insights.py check <ws> <files>` (path relative to this skill's folder)
on the post.

## Delivery

Show the post first. Send it to Slack (or elsewhere) only when the user asks and
names the channel. For a recurring run, the user can schedule this skill weekly.

`weekly-pulse.json`: `{"period", "metrics": {...}, "top_topics": [{"topic": "<parent topic id
exactly as in topics.json stats, e.g. billing>", "name": "<display name>",
"sessions", "share", "cx_positive_share", "change"}] (one entry per topic, ties included as separate entries),
"low_cx_drivers": [...], "actions": [...], "feature_requests": [...]}` — each entry
citing the result file it came from.
