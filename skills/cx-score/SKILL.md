---
name: cx-score
description: Score customer experience (1–5) for every closed Smartsupp chat session from the transcript itself — no survey needed — with the reasons behind each score (answer quality of AI and human, customer effort, emotion, product and policy feedback). Use for "CX score", "customer satisfaction", "sentiment of chats", "how happy are customers", or as input for topics and weekly pulse.
---

# CX score

A survey-free customer-experience score per chat session, modelled on Intercom's CX
Score: 1 (very negative) to 5 (very positive), 4–5 counts as positive. Survey ratings
cover a small, self-selected minority of chats; this reads every eligible one.

**Input:** `<ws>/digest.txt` (compact view of `sessions.redacted.jsonl`; see `smartsupp-conversations` → Working efficiently) from the `smartsupp-conversations` skill
(run it first if missing). **Output:** `<ws>/results/cx-score.jsonl` (one line per
session) and `<ws>/results/cx-score.md` (summary).

## 1. Eligibility

A session is scored only if all hold:
- `status` is `closed`;
- the customer started it (`initiated_by: customer`) — not a proactive message;
- the customer wrote at least one substantive message (not just "hi", "test",
  an emoji, or text clearly meant for someone else);
- the business replied at least once (operator, AI agent or bot) after it.

Otherwise write `{"session_id", "eligible": false, "ineligible_reason"}` and stop.
Abandoned chats where the customer left before any reply are ineligible.

## 2. Fact sheet (before judging answer quality)

A single transcript often cannot show that an AI answer is wrong. Build a short fact
sheet first: what human operators state across **all** sessions (prices, periods,
specs, procedures, what the business does not offer), plus `<ws>/kb/` if present and
`results/contradictions.json` if it exists. Where operators and the knowledge
disagree, operators win (they are the current truth). Judge every AI answer against
this sheet.

`answer_quality_ai` is **poor** when the AI, at least once in the session:
- states something the fact sheet contradicts (outdated price, wrong rule, invented
  spec), or guesses a fact with hedging ("probably", "usually", "I think") where
  operators give a definite answer;
- answers for the wrong business, or in a different language than the customer wrote;
- says it does not have the information (or offers a human for that reason) when the
  question is a general one operators answer elsewhere — a knowledge gap is a poor
  AI answer even if the handover offer is polite;
- promises an action it cannot perform (booking, forwarding, a deadline).

It is **good** when the answer matches the fact sheet, or when the AI correctly routes
something that inherently needs a human (order status, an individual case or account,
a complaint needing a decision).

## 3. Reasons (judge each independently from the transcript)

| Reason | Values | Meaning |
|---|---|---|
| `answer_quality_ai` | good / poor / n/a | Judged against the fact sheet (section 2). n/a if no AI message. |
| `answer_quality_operator` | good / poor / n/a | Same for human operators. |
| `effort` | low / high | High = customer repeated themselves, had to push or escalate, was bounced between AI and human more than once, or reports having tried several times already (e.g. "tried the code three times"). |
| `emotion` | positive / negative / neutral | Clear feelings in the customer's own words: gratitude, delight vs. frustration, anger, anxiety, sarcasm, threats to leave. Politeness alone is neutral. Mild regret about a "no" — "schade", "that's a shame", "would be nice though" — with no frustration aimed at the service is also `neutral`; record the wish as product/policy feedback instead. `negative` needs frustration, annoyance, anger, worry, sarcasm or a complaint ("that's ridiculous", "I've asked three times", "I'm worried"). Distress about the customer's own situation (a dismissal, a lawsuit) is `negative` emotion, but see the scoring rule below — it does not by itself make the service experience bad. |
| `product_feedback` | positive / negative / none | Praise or criticism of a product or service quality. |
| `policy_feedback` | positive / negative / none | Praise or criticism of rules: returns, shipping, fees, billing, scope. |
| `resolved` | yes / partial / no | Did the customer get what they came for (an answer, a next step, a fix)? |

## 4. Score

Start from the outcome, then adjust for the strongest signals:

| Score | Typical pattern |
|---|---|
| 5 | Resolved, low effort, and explicit positive emotion or praise. |
| 4 | Resolved, low effort, neutral tone. |
| 3 | Partially resolved, or resolved with friction (a poor answer first, mild disappointment, neutral answer to a complaint), or the outcome is "no, we don't do that" accepted calmly. |
| 2 | Unresolved, or high effort, or clear negative emotion / negative feedback even if a fix was offered. |
| 1 | Strong negative emotion together with high effort or an unresolved problem; the customer threatens to leave, demands a refund angrily, or insults. |

Rules:
- Negative emotion **about the service or outcome** (frustration with the answer,
  the policy, the product, the wait) caps the score at 3, strong anger at 2. Anxiety
  about the customer's own situation does not cap the score when the chat helped
  them (clear answer or next step) — score the service.
- "Resolved" includes a useful next step or alternative the customer accepts (a
  referral to a partner, another delivery option). A plain "no, we don't do that"
  accepted calmly is 3; one the customer is unhappy about is 2.
- A threat to leave ("I'll buy elsewhere") is 2, or 1 together with high effort,
  anger or an unresolved problem.
- Positive emotion at the end of a rough chat can lift by one.
- An AI-only chat that ends with the AI offering a human (or saying it does not know)
  and nobody answering is `resolved: no` for a general question the business should
  answer (score 2, or 3 if the customer reacts calmly) and `partial` when the AI routed
  a case that needs a human anyway (score 3).
- A correct human answer after a poor AI answer is `resolved: yes` with friction: 3,
  or 4 when the customer clearly ends satisfied.
- A customer survey rating (`rating.value`, 1/3/5) is a signal, not the answer.
  `rating_agrees` compares bands: 1–2 ↔ 1, 3 ↔ 3, 4–5 ↔ 5; `null` without a rating.

## 5. Process

Read sessions in batches of ~25 (whole transcripts, redacted). For each eligible
session write one JSON line:

```json
{"session_id": "…", "eligible": true, "score": 4,
 "reasons": {"answer_quality_ai": "n/a", "answer_quality_operator": "good", "effort": "low",
             "emotion": "neutral", "product_feedback": "none", "policy_feedback": "none", "resolved": "yes"},
 "explanation": "One or two sentences on why, no personal data.",
 "handled_by": "operator_only | ai_only | ai_and_operator",
 "rating": 5, "rating_agrees": true}
```

`handled_by` comes from who actually wrote replies (not who was assigned).

## 6. Summary (`cx-score.md`)

Get every number below from `python3 ../smartsupp-conversations/scripts/insights.py cx-summary <ws>`
(after writing cx-score.jsonl); add the paraphrases and examples yourself.

- CX score % (share of eligible sessions scoring 4–5), mean score, number scored vs.
  total; split by `handled_by`.
- Survey coverage: sessions with a rating vs. scored sessions, and agreement rate.
- Top negative drivers: count of negative reasons, each with 2–3 example
  `session_id`s and a one-line paraphrase (no personal data — apply the gate from
  `smartsupp-conversations`).
- Do not rank or score individual operators.

Optional write-back (only when the user asks): tag sessions in Smartsupp with
`cx-1`…`cx-5` using `create_tag` / `tag_conversation`.
