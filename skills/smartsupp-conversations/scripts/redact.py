#!/usr/bin/env python3
"""Deterministic personal-data redaction for chat transcripts (first layer).

Replaces personal data with typed placeholders such as [EMAIL] or [NAME]. It catches
structured identifiers by pattern and the contact's own name/email/phone by value
(including Czech/Slovak inflected forms of the name). It does NOT understand
context: names mentioned in passing, employers, health details, or amounts tied to a
person's case need the model pass described in SKILL.md (second layer).

Usage:
  redact.py <sessions.jsonl> <out.jsonl> [--contacts <dir>] [--kb <dir>] [--order-pattern REGEX]...
      Redacts every message; contact values come from <dir>/<contact_id>.json
      (get_contact results). Adds "redactions": {type: count} per session.
  redact.py --text "some text"   # quick check

Standard library only.
"""
import json
import os
import re
import sys
import unicodedata

UP = "A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽÄÔĹĽŔ"
LO = "a-záčďéěíňóřšťúůýžäôĺľŕ"
CITIES = (
    "Praha|Praze|Brno|Brně|Ostrava|Ostravě|Plzeň|Plzni|Olomouc|Olomouci|Liberec|Liberci|"
    "Pardubice|Pardubicích|Zlín|Zlíně|Kladno|Kladně|Opava|Opavě|Jihlava|Jihlavě|Bratislava|"
    "Bratislave|Košice|Košiciach|Žilina|Žiline|Nitra|Nitre|Prešov|Prešove|Trnava|Trnave|"
    "Banská Bystrica|Trenčín|Vienna|Wien|Prague|Hradec Králové|České Budějovice|Ústí nad Labem|"
    "Karlovy Vary|Kolín|Kutná Hora|Mladá Boleslav|Teplice|Děčín|Havířov|Frýdek-Místek"
)
CURRENCY_OR_UNIT = r"(?!\s?(?:Kč|CZK|EUR|€|mm|g|kg|cm|mAh|lm|%))"

PATTERNS = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    # National personal / tax ids: codice fiscale (IT), DNI/NIE (ES), NIR / n° de sécu (FR),
    # PESEL (PL, after a keyword), Steuer-ID (DE, after a keyword).
    ("NATIONAL_ID", re.compile(r"\b[A-Z]{6}\d{2}[A-EHLMPR-T]\d{2}[A-Z]\d{3}[A-Z]\b", re.I)),
    ("NATIONAL_ID", re.compile(r"\b(?:\d{8}|[XYZ]\d{7})-?[A-HJ-NP-TV-Z]\b(?![\w-])")),
    ("NATIONAL_ID", re.compile(r"\b[12]\s?\d{2}\s?(?:0[1-9]|1[0-2])\s?\d{2}\s?\d{3}\s?\d{3}(?:\s?\d{2})?\b")),
    ("NATIONAL_ID", re.compile(
        r"\b(?i:PESEL|Steuer-?ID|Steueridentifikationsnummer|codice\s+fiscale|C\.F\.|NIR|n°\s?de\s?sécu\w*|numéro\s+de\s+sécurité\s+sociale)"
        r"\s*:?\s*(?P<v>[A-Z0-9][A-Z0-9 ]{7,20}[A-Z0-9])\b")),
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[\dA-Z]{4}){3,7}(?:\s?[\dA-Z]{1,4})?\b")),
    ("CARD", re.compile(r"\b\d{4}(?:[ -]?\d{4}){3}\b")),
    ("BIRTH_NUMBER", re.compile(r"\b\d{6}/\d{3,4}\b")),
    ("COMPANY_ID", re.compile(r"\b(?:IČO|IČ|DIČ|ICO|DIC|IČ DPH)\s*:?\s*(?P<v>(?:CZ|SK)?\s?\d{8,10})\b", re.I)),
    # International company / tax ids after a keyword: "ID 01020304", "VAT No. DE000000000".
    ("COMPANY_ID", re.compile(
        r"\b(?:(?:company|business|tax)\s)?(?:ID|Reg(?:istration)?\.?\s?No\.?|VAT(?:\sID|\sNo\.?)?|USt-?IdNr\.?|NIF|CIF|NIP|KRS|EIN)"
        r"\s*:?\s*(?P<v>[A-Z]{0,2}\s?\d[\d-]{6,12}\d)\b")),
    ("COMPANY_ID", re.compile(r"\b(?:CZ|SK)\d{8,10}\b")),
    # Customer companies: "Vzor Trade s.r.o.", "Ukázka Retail a.s.", "Example Widgets LLC"
    ("COMPANY", re.compile(
        rf"\b(?:[{UP}][\w&.-]*\s){{1,4}}(?:s\.\s?r\.\s?o\.|spol\.\s?s\s?r\.\s?o\.|a\.\s?s\.|k\.\s?s\.|v\.\s?o\.\s?s\.|GmbH|Ltd\.?|Inc\.?|LLC|L\.L\.C\.|S\.L\.|S\.A\.|SAS|S\.p\.A\.|AG|B\.V\.|Sp\.\s?z\s?o\.o\.|Pty\.?\sLtd)(?!\w)")),
    ("ACCOUNT", re.compile(r"\b(?:\d{1,6}-)?\d{6,10}/\d{4}\b")),
    ("PHONE", re.compile(r"(?<![\w/])(?:\+\d{3}[\s.-]?)?\d{3}[\s.-]?\d{3}[\s.-]?\d{3}\b" + CURRENCY_OR_UNIT)),
    ("ORDER_ID", re.compile(r"\b[A-Z]{2,4}-\d{4}-\d{3,6}\b")),
    # Year-prefixed document numbers on their own: 2026-0001, 2026/0002
    ("DOC_NUMBER", re.compile(r"\b20\d{2}[-/]\d{3,6}\b")),
    ("DOC_NUMBER", re.compile(
        r"\b(?:faktur[a-zyáeěuo]{0,3}|invoice|smlouv[a-zyáeěuo]{0,3}|contract|objednávk[a-zyáeěuo]{0,3}|order)\s"
        r"(?:č\.\s?|číslo\s|no\.\s?|#)?(?P<v>[A-Z]{0,4}[-/]?\d[\d/-]{3,}\d)", re.I)),
    ("ADDRESS", re.compile(
        rf"\b[{UP}][{LO}]+(?:\s[{UP}]?[{LO}]+)?\s\d{{1,4}}(?:/\d{{1,4}}[a-z]?)?,\s*(?:\d{{3}}\s?\d{{2}}\s+)?(?:{CITIES})(?:\s\d{{1,2}})?")),
    # "Na Vzoru 9", "U Ukázky 8" (street names starting with a preposition)
    ("ADDRESS", re.compile(rf"\b(?:Na|U|V|K|Pod|Nad)\s[{UP}][{LO}]+(?:\s[{UP}]?[{LO}]+)?\s\d{{1,3}}(?:/\d{{1,4}})?\b(?!\s?[{LO}\d])")),
    # Czech/Slovak street names by their endings, any case: "Vzorovou 9", "Ukázková 8",
    # "Vzorného 7" (not followed by a unit).
    ("ADDRESS", re.compile(
        rf"\b[{UP}][{LO}]+(?:ová|ova|ovou|ové|ská|ské|skou|ní|ního|ním|ého|ská|cká|cké|ckou)\s\d{{1,3}}(?:/\d{{1,4}}[a-z]?)?\b"
        rf"(?!\s?(?:Kč|CZK|EUR|€|mm|g|kg|cm|mAh|lm|%|dn|let|km|ks|x\b))")),
    # International street addresses: "1 Example Road", "Calle Ejemplo 1",
    # "Musterstraße 1", "1 rue Exemple".
    ("ADDRESS", re.compile(
        r"\b\d{1,5}\s(?:[A-Z][a-z]+\s){1,3}(?:Street|St\.|Avenue|Ave\.?|Road|Rd\.|Lane|Ln\.|Drive|Dr\.|"
        r"Boulevard|Blvd\.?|Way|Court|Ct\.|Place|Pl\.|Grove|Close|Crescent|Terrace|Gardens|Row|Square|Mews|Walk|Hill)(?:,\s?(?:Apt|Suite|Unit)\.?\s?\w+)?")),
    ("ADDRESS", re.compile(
        r"\b(?:Calle|C/|Avenida|Avda\.|Plaza|Paseo|Carrer|Rua|Via|Viale|Rue|Avenue|Boulevard)\s"
        r"(?:(?:de|del|de la|de los|de las|da|do|des|du|della)\s)?[A-ZÁÉÍÓÚÑ][\wáéíóúñàèìòùç'-]+(?:\s[A-ZÁÉÍÓÚÑ][\wáéíóúñ-]+)?,?\s\d{1,4}\w?\b")),
    ("ADDRESS", re.compile(
        r"\b[A-ZÄÖÜ][a-zäöüß-]+(?:straße|strasse|str\.|weg|gasse|platz|allee|ring|damm)\s\d{1,4}\w?\b")),
    ("ADDRESS", re.compile(r"\b\d{1,4},?\s(?:rue|avenue|boulevard|chemin|place)\s(?:\w+\s){0,3}\w+", re.I)),
    # US "Anytown, XX 00000" and 5-digit postcodes directly before a capitalised city.
    ("POSTCODE", re.compile(r"\b[A-Z]{2}\s\d{5}(?:-\d{4})?\b")),
    ("POSTCODE", re.compile(r"\b\d{5}\b(?=\s[A-ZÁÉÍÓÚÄÖÜ][a-záéíóúäöüß]+)")),
    ("POSTCODE", re.compile(r"\b\d{3}\s\d{2}\b(?=\s+[" + UP + "])")),
    # UK postcodes: "AB1 2CD", "XY9 8ZW".
    ("POSTCODE", re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]?\s\d[A-Z]{2}\b")),
    # Identity documents after a keyword: passport, ID card (cs/sk/pl/de/es/fr/en).
    ("DOC_NUMBER", re.compile(
        r"\b(?i:passport|pass|pas|paszport|reisepass|personalausweis|pasaporte|DNI|NIE|passeport|"
        r"občansk\w*(?:\sprůkaz\w*)?|OP|dowód(?:\sosobisty)?|ID\scard|driving\slicen[cs]e|řidičsk\w*)"
        r"(?:\s(?i:no\.?|number|č\.|číslo|nr\.?|nummer|n\.?º))?\s*:?\s*(?P<v>[A-Z]{0,3}\s?\d{6,9}[A-Z]?)\b")),
    # Vehicle registration plates: "M-XY 1000" (DE), "1AB 0000" (CZ), "WA 00000" (PL), after a keyword or in DE form.
    ("PLATE", re.compile(r"\b[A-ZÄÖÜ]{1,3}-[A-Z]{1,2}\s?\d{1,4}[EH]?\b")),
    ("PLATE", re.compile(
        r"\b(?i:SPZ|RZ|Kennzeichen|registration|reg\.?\s?no\.?|tablica|rejestracja|matrícula|plaque|license\splate|licence\splate)"
        r"\s*:?\s*(?P<v>[A-Z0-9]{1,3}[\s-]?[A-Z0-9]{2,5}(?:[\s-]?\d{1,4})?)\b")),
    # International phone numbers in any grouping: "+44 20 0000 0000", "+49 30 0000000".
    ("PHONE", re.compile(r"(?<![\w+])\+(?=(?:[\s().-]*\d){8})\d{1,3}(?:[\s.-]?\(?\d{1,4}\)?){2,5}\b")),
    # Customer account / workspace ids: "WS-XX-0000", "ACC-00000" (not ISO-8601, UTF-8, RFC-…).
    ("ACCOUNT_ID", re.compile(r"\b(?!ISO|UTF|RFC|SHA|MD|COVID)[A-Z]{2,4}(?:-[A-Z]{2,3})?-\d{3,8}\b")),
    # Card last digits: "card ending 0000", "Karte endet auf 0000", "tarjeta terminada en 0000".
    ("CARD", re.compile(
        r"\b(?i:card|karte|karty|kartu|karta|tarjeta|carte)\b[^.\n\d]{0,25}?"
        r"(?i:ending(?:\sin)?|ends\sin|endet\sauf|končí(?:cí)?(?:\sna)?|terminada\sen|se\stermina\spar|last\s(?:four|4)(?:\sdigits)?)\s?:?\s?(?P<v>\d{4})\b")),
    # Courtesy titles followed by a capitalised name: "paní Vzorová", "pane Vzorku", "Ing. Ukázková",
    # "Monsieur Exemple", "Mme Exemple", "Signora Esempio", "Herr Muster", "Sra. Ejemplo".
    ("NAME", re.compile(
        rf"\b(?:pan|pane|paní|pani|slečno|slečna|Mr\.?|Mrs\.?|Ms\.?|Ing\.|Mgr\.|MUDr\.|JUDr\.|Bc\.|"
        rf"Monsieur|Madame|Mademoiselle|M\.|Mme\.?|Mlle\.?|Signor|Signora|Signorina|Sig\.(?:ra|na)?|Dott\.(?:ssa)?|"
        rf"Herr|Frau|Señor|Señora|Sr\.|Sra\.|Dr\.)\s"
        rf"(?P<v>[{UP}][{LO}]+(?:[\s-][{UP}][{LO}]+)?)")),
    # Self-introductions: "jmenuji se Eva Vzorová", "jsem Luděk Vzorek", "my name is ...", "je m'appelle ...".
    ("NAME", re.compile(
        rf"\b(?i:jmenuji se|jmenujem sa|jméno je|jsem|som|my name is|name is|name:|jméno:|I am|I'm|"
        rf"je m'appelle|mi chiamo|me llamo|ich heiße|ich heisse)\s(?!(?:Apple|Google|Samsung|Amazon|PayPal)\s)(?P<v>[{UP}][{LO}]+[\s-][{UP}][{LO}]+)")),
    # Bookings in someone's name: "a nome Maria Esempio", "au nom de Jean Exemple", "under the name ...".
    ("NAME", re.compile(
        rf"\b(?i:a nome(?: di)?|al nome di|au nom de|sous le nom de|under the name(?: of)?|in the name of|"
        rf"auf den Namen|na jméno|a nombre de)\s(?P<v>[{UP}][{LO}]+(?:[\s-][{UP}][{LO}]+){{0,2}})")),
    # Street names without a house number: "avenue Exemple", "rue Exemple", "corso Esempio"
    # ("via" only with a number, above: "via Settings", "via Microsoft Teams" are not streets).
    ("ADDRESS", re.compile(
        r"\b(?i:rue|avenue|boulevard|bd|chemin|allée|impasse|quai|viale|corso|piazza|vicolo|calle|avenida)\s"
        r"(?:(?:de la|de l'|des|du|de|della|dell'|del|dei|degli|delle)\s?)?"
        r"(?!(?:WhatsApp|Apple|Google|Microsoft|Smartsupp|Slack|Signal|Telegram|Viber|Facebook|Messenger|Instagram|SMS|E-?mail|PayPal|Stripe|Zoom|Teams|Skype|Internet|Web)\b)"
        r"[A-ZÀ-Ý][\wà-ÿ'-]+(?:\s\d{1,4}\w?)?")),
]
# A customer reply that starts with "First Last" right after the business asked for a name.
NAME_ASK = re.compile(r"(?i)\b(?:nom|name|nome|jméno|jmeno|Namen|nombre|meno)\b")
LEADING_NAME = re.compile(rf"^\s*(?:(?i:ok|okay|yes|sure|oui|d'accord|sì|si|certo|va bene|ano|jo|ja|sí|vale)[,.!]?\s+)?(?P<v>[{UP}][{LO}]+(?:[\s-][{UP}][{LO}]+){{1,2}})(?=\s*(?:[,.;:!]|$|\s[{LO}\d]))")


def _strip(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()


def name_regex(full_name):
    """Match a person's name tokens including Czech/Slovak case endings
    (Vzorek -> Vzorku, Vzorkovi; Vzorová -> Vzorové; Ukázka -> Ukázko)."""
    alts = []
    for tok in re.split(r"\s+", full_name or ""):
        tok = tok.strip(".,")
        if len(tok) < 3 or tok.endswith(".") or tok.lower() in ("ing", "mgr", "bc", "judr", "mudr"):
            continue
        stem = tok[:-1] if len(tok) > 4 and tok[-1].lower() in "aeiouyáéíóúůý" else tok
        # Diacritics optional: customers often type "Ludek Vzorovy" for "Luděk Vzorový".
        body = "".join(f"[{re.escape(c)}{re.escape(_strip(c))}]" if _strip(c) != c.lower() else re.escape(c)
                       for c in stem)
        alts.append(body + rf"[{LO}a-z]{{0,4}}")
    if not alts:
        return None
    return re.compile(r"\b(?:" + "|".join(alts) + r")\b")


def known_value_patterns(contact):
    pats = []
    if not contact:
        return pats
    if contact.get("email"):
        pats.append(("EMAIL", re.compile(re.escape(contact["email"]), re.I)))
    if contact.get("phone"):
        digits = re.sub(r"\D", "", contact["phone"])
        if len(digits) >= 9:
            pats.append(("PHONE", re.compile(r"[\s.-]?".join(re.escape(d) for d in digits[-9:]))))
    rx = name_regex(contact.get("name"))
    if rx:
        pats.append(("NAME", rx))
    return pats


def kb_corpus(kb_dir):
    """Lower-cased text of the business's own knowledge (kb/*.md|txt): a match found
    there (the clinic's street, its booking e-mail) is business data, not personal."""
    if not kb_dir or not os.path.isdir(kb_dir):
        return ""
    return "\n".join(open(os.path.join(kb_dir, fn), encoding="utf-8").read()
                     for fn in sorted(os.listdir(kb_dir)) if fn.endswith((".md", ".txt"))).lower()


def redact_text(text, extra=(), counts=None, keep=frozenset(), kb_text=""):
    if not text:
        return text
    for label, rx in list(extra) + PATTERNS:
        def sub(m, label=label):
            hit = m.group(0).strip().lower()
            if hit in keep or (label not in ("NAME",) and len(hit) > 5 and hit in kb_text):
                return m.group(0)
            if counts is not None:
                counts[label] = counts.get(label, 0) + 1
            if "v" in m.re.groupindex:  # keep the context words, replace only the value
                a, b = m.span("v")
                return m.group(0)[: a - m.start()] + f"[{label}]" + m.group(0)[b - m.start():]
            return f"[{label}]"
        text = rx.sub(sub, text)
    return text


CONSTANT_LABELS = {"EMAIL", "PHONE", "ADDRESS"}
MIN_SESSIONS = 3


def business_constants(sessions, contacts_dir=None):
    """Emails/phones the business itself gives out: written by operators or the AI
    agent in at least MIN_SESSIONS different sessions and never a contact's own value.
    These are kept (e.g. a claims address), everything else is redacted."""
    seen = {}
    for s in sessions:
        for m in s["messages"]:
            if m["role"] not in ("operator", "ai_agent", "bot"):
                continue
            for label, rx in PATTERNS:
                if label not in CONSTANT_LABELS:
                    continue
                for hit in rx.finditer(m["text"] or ""):
                    seen.setdefault(hit.group(0).strip().lower(), set()).add(s["session_id"])
    contact_vals = set()
    if contacts_dir and os.path.isdir(contacts_dir):
        for fn in os.listdir(contacts_dir):
            c = json.load(open(os.path.join(contacts_dir, fn), encoding="utf-8"))
            contact_vals |= {str(c.get(k) or "").strip().lower() for k in ("email", "phone")}
    return frozenset(v for v, ss in seen.items() if len(ss) >= MIN_SESSIONS and v not in contact_vals)


def main():
    if "--text" in sys.argv:
        print(redact_text(sys.argv[sys.argv.index("--text") + 1]))
        return
    args = sys.argv[1:]
    contacts_dir = None
    kb_dir = None
    order_pats = []
    pos = []
    i = 0
    while i < len(args):
        if args[i] == "--contacts":
            contacts_dir = args[i + 1]; i += 2
        elif args[i] == "--kb":
            kb_dir = args[i + 1]; i += 2
        elif args[i] == "--order-pattern":
            order_pats.append(("ORDER_ID", re.compile(args[i + 1]))); i += 2
        else:
            pos.append(args[i]); i += 1
    src, dst = pos
    sessions = [json.loads(line) for line in open(src, encoding="utf-8")]
    keep = business_constants(sessions, contacts_dir)
    kb_text = kb_corpus(kb_dir)
    if keep:
        print("kept as business data:", ", ".join(sorted(keep)))
    total = {}
    with open(dst, "w", encoding="utf-8") as out:
        for s in sessions:
            contact = None
            if contacts_dir and s.get("contact_id"):
                p = os.path.join(contacts_dir, s["contact_id"] + ".json")
                if os.path.exists(p):
                    contact = json.load(open(p, encoding="utf-8"))
            extra = known_value_patterns(contact) + order_pats
            counts = {}
            asked_name = False
            for m in s["messages"]:
                text = m["text"]
                if asked_name and m["role"] == "customer" and text:
                    hit = LEADING_NAME.match(text)
                    if hit:
                        a, b = hit.span("v")
                        text = text[:a] + "[NAME]" + text[b:]
                        counts["NAME"] = counts.get("NAME", 0) + 1
                if m["role"] != "customer":
                    asked_name = bool(NAME_ASK.search(text or ""))
                m["text"] = redact_text(text, extra, counts, keep, kb_text)
            if s.get("rating") and s["rating"].get("text"):
                s["rating"]["text"] = redact_text(s["rating"]["text"], extra, counts, keep, kb_text)
            s["redactions"] = counts
            for k, v in counts.items():
                total[k] = total.get(k, 0) + v
            out.write(json.dumps(s, ensure_ascii=False) + "\n")
    print("redactions:", json.dumps(total, ensure_ascii=False))


if __name__ == "__main__":
    main()
