#!/usr/bin/env python3
"""Fail if personal data from the workspace appears in files meant to be published.

Collects sensitive values from the un-redacted sessions (every span the redaction
patterns match) and from contacts/ (name tokens, email, phone), then searches the
given files for them, ignoring case, diacritics and whitespace differences.

Usage: leakcheck.py <workspace> <file>... [--allow VALUE]...
Exit code 1 and a list of hits when anything leaks.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from redact import PATTERNS, _strip, business_constants  # noqa: E402

MIN_LEN = 4


def norm(s):
    return re.sub(r"[\s.\-/]+", "", _strip(s))


def words(s):
    """Lower-case, no diacritics, punctuation -> single spaces, padded for word matching."""
    return " " + re.sub(r"[^0-9a-z@]+", " ", _strip(s)).strip() + " "


def found(value, text_words, text_compact):
    # Numbers (phones, IBANs, ids) may be written with any spacing: compare compactly.
    if sum(c.isdigit() for c in value) >= 4:
        return norm(value) in text_compact
    # Names, addresses, emails: whole words only ("Ivo" must not match "give old").
    return words(value) in text_words


def common_words(ws):
    """Lower-case words the business itself uses (operator and AI messages, kb/): a contact
    name token that is also one of these ("Rose", "Bill", "Will") is checked only when
    capitalised, so ordinary text ("the price is …") does not count as a leak."""
    seen = set()
    sp = os.path.join(ws, "sessions.jsonl")
    if os.path.exists(sp):
        for line in open(sp, encoding="utf-8"):
            for m in json.loads(line)["messages"]:
                if m.get("role") in ("operator", "ai_agent", "bot"):
                    seen.update(re.findall(r"(?<![\w])([a-zà-ž]{4,})(?![\w])", m.get("text") or ""))
    kb = os.path.join(ws, "kb")
    if os.path.isdir(kb):
        for fn in os.listdir(kb):
            seen.update(re.findall(r"(?<![\w])([a-zà-ž]{4,})(?![\w])", open(os.path.join(kb, fn), encoding="utf-8").read()))
    return seen


def sensitive_values(ws):
    vals = set()
    cased = set()  # name tokens that are also common words: match only capitalised
    common = common_words(ws)
    cdir = os.path.join(ws, "contacts")
    if os.path.isdir(cdir):
        for fn in os.listdir(cdir):
            c = json.load(open(os.path.join(cdir, fn), encoding="utf-8"))
            for k in ("email", "phone"):
                if c.get(k):
                    vals.add(c[k])
            for tok in re.split(r"\s+", c.get("name") or ""):
                if len(tok) >= MIN_LEN and not tok.endswith("."):
                    (cased if tok.lower() in common else vals).add(tok)
    sp = os.path.join(ws, "sessions.jsonl")
    if os.path.exists(sp):
        sessions = [json.loads(line) for line in open(sp, encoding="utf-8")]
        keep = business_constants(sessions, cdir)
        for s in sessions:
            for m in s["messages"]:
                for _label, rx in PATTERNS:
                    for hit in rx.finditer(m["text"] or ""):
                        v = hit.group("v") if "v" in rx.groupindex else hit.group(0)
                        if len(norm(v)) >= MIN_LEN and v.strip().lower() not in keep:
                            vals.add(v)
    return vals, cased


def main():
    args = sys.argv[1:]
    allow = set()
    files = []
    i = 1
    ws = args[0]
    while i < len(args):
        if args[i] == "--allow":
            allow.add(norm(args[i + 1])); i += 2
        else:
            files.append(args[i]); i += 1
    # The business's own data (its name, staff, addresses, contacts) is in its knowledge
    # export: anything found there is not personal data.
    kb_text = ""
    kdir = os.path.join(ws, "kb")
    if os.path.isdir(kdir):
        kb_text = " ".join(open(os.path.join(kdir, f), encoding="utf-8").read() for f in os.listdir(kdir))
    kb_w, kb_c = words(kb_text), norm(kb_text)
    raw_vals, cased = sensitive_values(ws)
    vals = {v for v in raw_vals if norm(v) not in allow and not found(v, kb_w, kb_c)}
    cased = {v for v in cased if norm(v) not in allow}
    hits = []
    for f in files:
        text = open(f, encoding="utf-8").read()
        tw, tc = words(text), norm(text)
        for v in sorted(vals):
            if norm(v) and found(v, tw, tc):
                hits.append((f, v))
        for v in sorted(cased):  # e.g. surname "Rose": only a capitalised mention counts
            if re.search(r"(?<![\w])" + re.escape(v[0].upper() + v[1:]) + r"(?![\w])", text):
                hits.append((f, v))
    if hits:
        for f, v in hits:
            print(f"LEAK {f}: {v}")
        sys.exit(1)
    print(f"ok — {len(files)} file(s), {len(vals) + len(cased)} sensitive values checked")


if __name__ == "__main__":
    main()
