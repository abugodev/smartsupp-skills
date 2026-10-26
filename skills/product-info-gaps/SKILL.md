---
name: product-info-gaps
description: Find which details of what a business offers — products, room types, plans, packages, services — customers keep asking about in Smartsupp chat because the offering's page does not say (size charts, materials, battery life, room size, bed setup, plan limits…), and draft the missing page copy. Works for e-shops and any business that presents offerings on its website. Use for "missing product information", "what's missing on product pages", "PDP gaps", "product questions from chat".
---

# Product info gaps

Questions about an offering in chat are a to-do list for the page that presents it:
each repeated question is an attribute the page should state. An **offering** is one of
the things customers choose between, each presented on its own page or card — a product
in an e-shop, a room type in a hotel, a plan in SaaS, a course or package elsewhere.
Product info means **properties of the thing itself** — what it is, what it has, what
fits or is allowed in it. Commercial terms and processes (price, fees, delivery or processing
time, how to order or book, policies) are not product info even when asked about
one offering: they are knowledge gaps (→ knowledge-gaps). **Bookable services with a fixed
format are offerings too**: treatments, therapies, classes, courses, tours, session packs,
visits, assessments — each with its own card or page. Their format, duration, who it is for,
what is included, where and when it is available, validity and contraindications are product
info. Services whose deliverable is tailored advice or work (legal,
consulting, agencies) usually have no product-info gaps, and the business's
general facilities and services (parking, transfers, restaurant or spa hours) are not
offerings either. Product info is what a buyer checks **before choosing** — what the
offering has, includes, allows and its limits (room has air conditioning, Team includes
25 staff, SAML only in Pro). **How to use** it after buying — setup steps, file formats
for an import, how settings or displays behave (how shift times show across time
zones) — is help-centre knowledge (→ knowledge-gaps), even when asked about one
offering. Care, fit and sizing guidance stay product info: offering pages normally
carry them.

**Input:** `<ws>/digest.txt` (compact view of `sessions.redacted.jsonl`; see `smartsupp-conversations` → Working efficiently) (customer messages carry the page they
were sent from in `pages`); optional product data `<ws>/products/*` (feed, page
text). **Output:** `<ws>/results/product-info-gaps.json`, `<ws>/results/product-info-gaps.md`.

## Process

1. Keep sessions where the customer asks about a **property of an offering** — specs,
   size/fit, dimensions, capacity, equipment, materials, care, compatibility,
   suitability for a use, what is included, who or what is allowed (e.g. pets in a room
   type), accessibility. Not offering questions: order or
   booking status, delivery, payment, availability on a date or stock levels
   (transient), general policies that apply to everything (→ knowledge-gaps), praise or
   complaints (→ feedback-drafts).
2. Identify the offering: from the page path (`/products/trail-runner-2` →
   `trail-runner-2`, `/rooms/deluxe` → `deluxe-room`) or the offering named in the
   message. Use a stable slug; when a question concerns all offerings of one kind
   ("do the rooms have air conditioning?"), use the kind as the slug (`rooms`).
3. Name the attribute in a normalised form (`size-chart`, `waterproof-rating`,
   `battery`, `weight`, `materials`, `compatibility`, `care`, `dimensions`…). Several
   questions about the same attribute are one gap.
   One gap = one attribute a shopper would look for in one place on the page
   (e.g. charging time and battery life are one "battery" spec; sleeve length belongs
   to "size-chart"). A session asking about two attributes counts for both.
4. Check whether the product data (`<ws>/products/*`, else the AI knowledge in
   `<ws>/kb/`) already states it → if yes, mark
   `on_page: true` (the problem is findability, not missing data).
5. Take the answer operators gave (if any) and draft product-page copy: one short
   paragraph or a small table, the business's language, exact numbers. Mark
   `needs_input` when no one answered.
6. Personal-data gate, then `python3 ../smartsupp-conversations/scripts/insights.py check <ws> <files>` (path relative to this skill's folder) on the outputs.

## Output

```json
{"gaps": [{"product": "espresso-pro-x", "attribute": "water-tank-capacity", "count": 5,
           "sessions": ["…"], "example_questions": ["…"], "on_page": false,
           "suggested_copy": "…", "status": "draft|needs_input"}]}
```
`product-info-gaps.md`: table product × attribute × count (most asked first), then the
suggested copy per gap.
