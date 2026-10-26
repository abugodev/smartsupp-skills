---
name: knowledge-gaps
description: Find what the Smartsupp AI agent could not answer, why it handed chats over to humans, and draft knowledge articles from the answers human operators gave — with personal and one-off information removed so only reusable knowledge remains. Use for "knowledge gaps", "what the bot didn't know", "handover reasons", "improve the AI chatbot", "draft FAQ/knowledge from chats".
---

# Knowledge gaps → article drafts

Modelled on Intercom's content-gap suggestions: look where the AI failed (or where
humans had to answer because there was no AI yet), take the answer the human gave,
and turn recurring questions into knowledge the AI can use — but only knowledge that
is true for every customer.

**Input:** `<ws>/digest.txt` (compact view of `sessions.redacted.jsonl`; see `smartsupp-conversations` → Working efficiently); optional current knowledge in
`<ws>/kb/*.md|txt` (export of the AI agent's text sources, FAQ, web pages); optional
`<ws>/results/topics.json`.
**Output:** `<ws>/results/knowledge-gaps.json`, `<ws>/results/knowledge-gaps.md`, and
one draft per article in `<ws>/results/drafts/<gap-id>.md`.

## 1. Candidates

Go through every session with a customer question and collect **question → answer**
pairs:

- **AI failed:** the AI agent said it does not know / cannot help / offered a human,
  gave a wrong or vague answer that a human corrected, or the customer had to ask
  again or asked for a human. The human operator's reply that followed is the answer.
- **Human-only chats** (no AI agent involved — e.g. before the AI was launched):
  every customer question a human answered is a candidate.
- Questions nobody answered are gaps without an answer: list them, no draft.

## 2. Handover reasons (every session where a human replied after the AI)

One of: `missing_knowledge` (AI lacked the information), `wrong_answer` (AI answered
but was wrong / corrected), `customer_requested_human`, `account_specific` (needs
order/case data the AI cannot see), `complaint_or_emotion` (upset customer, claim,
refund), `action_required` (booking, cancellation, change that a human must do),
`other`. Count them.

## 3. Classify each candidate

| Class | Rule | Draft? |
|---|---|---|
| `generalizable` | The answer states a fact, price, policy, procedure, product property or rule that holds for every customer asking the same question. | yes |
| `covered` | The current knowledge (kb/) already answers it correctly. If kb/ is missing, judge by whether the AI answered it correctly in other sessions. If kb/ has the correct answer **and** an outdated duplicate (an old FAQ line), it is still `covered` — report "delete the stale line" as a kb fix (→ contradiction-finder). If kb/ states **only** a wrong value, it is `generalizable`: draft the corrected article and flag the kb conflict. | no (but report if the AI still failed → retrieval/wording issue) |
| `account_specific` | Depends on one customer's order, invoice, booking, account or case status. Complaints and disputes about the customer's own case stay here even when they recur (several disputed invoices, several late orders): how an operator *handled* a case ("I'll send you a breakdown and correct the invoice") is not a rule. Extract a `generalizable` gap only when an operator *states* a rule that applies to everyone ("every invoice can come with an itemised breakdown on request", "claims are settled within 30 days"). | no |
| `transient` | True only now (stock, restock dates, temporary outages). | no |
| `personal_matter` | Advice about one person's situation with no reusable rule. If a general rule is inside (e.g. a statutory deadline, an eligibility condition), extract the rule as `generalizable` and drop the person. | partly |
| `personal_matter` (clinical) | Health, medical or therapy advice given to one patient about their symptoms or treatment ("more pain after the first session — is that normal?") is always `personal_matter`, even when it sounds general: it needs a clinician's review, not a chatbot article. This covers advice about one person's symptoms or treatment only — a service the business offers for a health need (fragrance-free bedding on request, allergy-safe meals, step-free rooms, what to bring to a first appointment) is a general rule and stays `generalizable`. | no |
| `feature_request` | The customer asks whether something exists or asks for something the business does not offer. It always goes to `feedback-drafts`. It is **also** a gap (an article for the AI chatbot's own knowledge) only when the reply gives the customer something they can **do now** that the chatbot should repeat: an alternative or where to get it instead ("no braces here — a pharmacy or orthopaedic shop has them; our physio can advise which"), a workaround ("no exercise videos yet — your physio can film them on your phone"), a practical tip ("reminders are email only — add our address to your contacts"). A reply that only restates the status quo ("we send documents by email", "we'll look at it first thing Monday") is feedback only. Never write an article that lists options the business does **not** support (payment methods it doesn't take, countries it doesn't ship to): if kb/ lists the supported ones, the question is `covered`. | only with an actionable alternative |
| `out_of_scope` | Not a customer question about the business's offer: job applications, supplier or partnership offers, press, messages meant for someone else. | no |

Personal data is already replaced by `[TYPE]` placeholders in the input, but pattern
matching misses names typed without a title, employers, health details and amounts
of a personal case — treat any such detail you notice as personal data too.

## 4. Group into gaps

Group generalizable candidates that ask the same thing (any wording, any language)
into one gap. Per gap: `gap_id` (kebab-case), question as customers phrase it, number
of sessions, `session_ids`, handover reasons involved.

- **One session can hold several gaps.** Check every operator answer in the session,
  not only the reply to the opening question: a side question ("and is breakfast
  allergy-safe?") answered with a general rule is its own candidate.
- **One gap = one help article.** Group at the level of the article a customer would
  look for: everything one article would cover stays together (garage price, height
  limit and reservation → "Parking"; a headlamp's battery type, runtime and charging →
  one "battery" article; sauna and pool rules for children → "Wellness and children").
  For products, write one article per attribute group a customer looks up (size chart,
  care, battery, waterproofing, resoling) — never one article per product that bundles
  unrelated attributes. Make a
  separate gap only for a distinct service or feature that would get its own article
  title, even if it sits next to another topic (EV charging is not "Parking"; an
  allergy-safe breakfast is not "Breakfast times").

## 5. Draft one article per gap

Mark each gap's `evidence`: **confident** when an operator states the rule in two or more
sessions, or states it once as an explicit general rule ("we always…", "every invoice…");
**borderline** when it rests on one session and is implied from how a case was handled, or
the only answer is an alternative to something not offered. Draft both; list borderline gaps
in their own section of the .md so the team can publish confident ones directly and review
the rest.

- Language: the language the business uses with most customers (usually the
  operators' language). Keep numbers, units and prices exactly as operators wrote them.
- Title = the question. Body = the consolidated answer: every fact the operators gave
  that holds for everyone, plus conditions and exceptions. Short (≤ 120 words), plain,
  no greeting, no sign-off.
- If operators gave **different** answers to the same question, do not pick one —
  mark the article `needs_review` and list the conflicting statements.
- Apply the **personal-data gate** from the `smartsupp-conversations` skill: no names,
  contact data, order/invoice numbers, addresses, employers, health or financial
  details of individuals, amounts tied to one case, `[PLACEHOLDER]` tokens. Abstract
  personal cases into general rules or drop them. Never reuse a customer's own figures
  (their price, amount, date) as a worked example — state the rule, or use a neutral round
  example that does not appear in any chat.
- Run `python3 ../smartsupp-conversations/scripts/insights.py check <ws> <files>` (path relative to this skill's folder) on all drafts; fix until it passes.

## 6. Output

`knowledge-gaps.json`:
```json
{"handover_reasons": {"<session_id>": "missing_knowledge"},
 "gaps": [{"gap_id": "late-checkout", "question": "Can I check out later than 11:00?",
           "class": "generalizable", "evidence": "confident|borderline", "sessions": ["…"], "count": 4,
           "article": {"title": "…", "body": "…", "status": "draft|needs_review"}}],
 "excluded": [{"session_id": "…", "class": "account_specific|transient|personal_matter|covered|feature_request|out_of_scope", "note": "…"}],
 "unanswered": [{"question": "…", "sessions": ["…"]}]}
```
`knowledge-gaps.md`: gaps ranked by count with the draft text, handover-reason
counts, excluded classes with counts. Drafts stay drafts — publishing them to the AI
agent's knowledge is a separate, human-approved step.
