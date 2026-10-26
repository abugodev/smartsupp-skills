#!/usr/bin/env python3
"""Deterministic numbers for the insight skills — use these instead of writing helper scripts.

    insights.py cx-summary   <ws>          numbers for cx-score.md (JSON to stdout)
    insights.py topic-stats  <ws>          fills "stats" in results/topics.json from its
                                           taxonomy + assignments and results/cx-score.jsonl;
                                           prints the parent → subtopic table (markdown)
    insights.py pulse-metrics <ws>         every number weekly-pulse needs (JSON), ties marked
    insights.py check <ws> <file>...       JSON parses, every cited session id exists,
                                           no [PLACEHOLDER] tokens, then leakcheck

All judgement stays with the skill; these only count.
"""
import json
import os
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
STRENGTH = {"mention": 1, "ask": 2, "demand": 3, "churn-threat": 4}


def load_sessions(ws):
    return [json.loads(l) for l in open(os.path.join(ws, "sessions.redacted.jsonl"), encoding="utf-8")]


def load_cx(ws):
    p = os.path.join(ws, "results", "cx-score.jsonl")
    return [json.loads(l) for l in open(p, encoding="utf-8")] if os.path.exists(p) else []


def handled_by(s):
    st = s.get("stats") or {}
    ai, op = st.get("ai_messages", 0) > 0, st.get("operator_messages", 0) > 0
    return {(True, True): "ai_and_operator", (True, False): "ai_only",
            (False, True): "operator_only", (False, False): "none"}[(ai, op)]


def pct(a, b):
    return round(100 * a / b, 1) if b else None


def cx_block(rows):
    sc = [r for r in rows if r.get("eligible") and isinstance(r.get("score"), (int, float))]
    pos = sum(r["score"] >= 4 for r in sc)
    return {"scored": len(sc), "cx_positive_pct": pct(pos, len(sc)),
            "mean": round(statistics.mean(r["score"] for r in sc), 2) if sc else None}


def cx_summary(ws):
    rows = load_cx(ws)
    sc = [r for r in rows if r.get("eligible")]
    out = {"sessions": len(rows), "ineligible": len(rows) - len(sc), **cx_block(rows),
           "distribution": dict(sorted(Counter(r.get("score") for r in sc).items())),
           "by_handled_by": {h: cx_block([r for r in sc if r.get("handled_by") == h])
                             for h in sorted({r.get("handled_by") for r in sc})}}
    rated = [r for r in sc if r.get("rating") is not None]
    out["survey"] = {"rated": len(rated), "coverage_pct": pct(len(rated), len(sc)),
                     "agree": sum(bool(r.get("rating_agrees")) for r in rated),
                     "agree_pct": pct(sum(bool(r.get("rating_agrees")) for r in rated), len(rated))}
    neg = {"answer_quality_ai": "poor", "answer_quality_operator": "poor", "effort": "high",
           "emotion": "negative", "product_feedback": "negative", "policy_feedback": "negative",
           "resolved": ("no", "partial")}
    drivers = {}
    for k, bad in neg.items():
        ids = [r["session_id"] for r in sc if (r.get("reasons") or {}).get(k) in ((bad,) if isinstance(bad, str) else bad)]
        drivers[k] = {"count": len(ids), "examples": ids[:3]}
    out["negative_drivers"] = dict(sorted(drivers.items(), key=lambda kv: -kv[1]["count"]))
    if any("business" in r for r in sc):
        out["by_business"] = {b: cx_block([r for r in sc if r.get("business") == b])
                              for b in sorted({r.get("business") for r in sc if r.get("business")})}
    return out


def parent_of(node_id, tax):
    n = tax.get(node_id) or {}
    if n.get("parent"):
        return n["parent"]
    return node_id.rsplit("/", 1)[0] if "/" in node_id else node_id


def topic_stats(ws):
    p = os.path.join(ws, "results", "topics.json")
    t = json.load(open(p, encoding="utf-8"))
    tax = {n["id"]: n for n in t.get("taxonomy", [])}
    assign = t.get("assignments", {})
    if isinstance(assign, list):
        assign = {a["session_id"]: a for a in assign}
    cx = {r["session_id"]: r.get("score") for r in load_cx(ws) if r.get("eligible")}
    total = len(assign)
    groups = defaultdict(list)
    for sid, a in assign.items():
        sub = a.get("topic")
        groups[("subtopic", sub)].append(sid)
        groups[("parent", parent_of(sub, tax))].append(sid)
    stats = []
    for (level, topic), ids in groups.items():
        scores = [cx[s] for s in ids if cx.get(s) is not None]
        stats.append({"topic": topic, "level": level, "name": (tax.get(topic) or {}).get("name"),
                      "sessions": len(ids), "share": round(len(ids) / total, 3) if total else 0,
                      "cx_scored": len(scores),
                      "cx_positive_share": round(sum(x >= 4 for x in scores) / len(scores), 3) if scores else None,
                      "cx_mean": round(statistics.mean(scores), 2) if scores else None})
    stats.sort(key=lambda r: (r["level"] != "parent", -r["sessions"]))
    t["stats"] = stats
    json.dump(t, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    def row(r, parent):
        pos = "—" if r["cx_positive_share"] is None else "%.0f%%" % (100 * r["cx_positive_share"])
        name = r["name"] or r["topic"]
        cells = ("**%s**" % name, "") if parent else ("", name)
        return "| %s | %s | %d | %.0f%% | %s | %s |" % (cells + (r["sessions"], 100 * r["share"], pos, r["cx_mean"] or "—"))
    lines = ["| parent | subtopic | sessions | share | CX positive | CX mean |", "|---|---|---|---|---|---|"]
    for par in [r for r in stats if r["level"] == "parent"]:
        lines.append(row(par, True))
        for sub in [r for r in stats if r["level"] == "subtopic" and parent_of(r["topic"], tax) == par["topic"]]:
            lines.append(row(sub, False))
    return "\n".join(lines)


def top_with_ties(items, key, n):
    """First n items by key, plus every item tied with the n-th."""
    items = sorted(items, key=key, reverse=True)
    if len(items) <= n:
        return items, False
    cut = key(items[n - 1])
    top = [i for i in items if key(i) >= cut]
    return top, len(top) > n


def first_response(sessions):
    def ts(x):
        return datetime.fromisoformat(x.replace("Z", "+00:00"))
    anyr, human = [], []
    for s in sessions:
        msgs = [m for m in s.get("messages", []) if m.get("text")]
        c = next((m for m in msgs if m["role"] == "customer"), None)
        if not c:
            continue
        r = next((m for m in msgs if m["role"] in ("ai_agent", "bot", "operator") and ts(m["at"]) >= ts(c["at"])), None)
        o = next((m for m in msgs if m["role"] == "operator" and ts(m["at"]) >= ts(c["at"])), None)
        if r:
            anyr.append((ts(r["at"]) - ts(c["at"])).total_seconds())
        if o:
            human.append((ts(o["at"]) - ts(c["at"])).total_seconds())
    med = lambda v: round(statistics.median(v)) if v else None
    return {"median_first_reply_s": med(anyr), "median_first_human_reply_s": med(human),
            "chats_with_human_reply": len(human), "source": "transcripts"}


def rjson(ws, name):
    p = os.path.join(ws, "results", name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def pulse_metrics(ws):
    sessions = load_sessions(ws)
    split = Counter(handled_by(s) for s in sessions)
    starts = sorted(s["started_at"] for s in sessions if s.get("started_at"))
    out = {"period": {"first": starts[0] if starts else None, "last": starts[-1] if starts else None},
           "chats": len(sessions), "handled_by": dict(split),
           "handled_by_pct": {k: pct(v, len(sessions)) for k, v in split.items()},
           "first_response": first_response(sessions), "cx": cx_block(load_cx(ws))}
    t = rjson(ws, "topics.json")
    if t:
        parents = [r for r in t.get("stats", []) if r.get("level") == "parent"
                   and not re.search(r"(^|/)(other|autre|altro|sonstige|ostatni)$", r["topic"], re.I)]
        top, tie = top_with_ties(parents, lambda r: r["sessions"], 5)
        out["top_topics"] = {"items": [{k: r.get(k) for k in ("topic", "name", "sessions", "share", "cx_positive_share")} for r in top],
                             "tie_at_cutoff": tie}
    kg = rjson(ws, "knowledge-gaps.json")
    if kg:
        gaps = [g for g in kg.get("gaps", []) if g.get("class", "generalizable") == "generalizable"]
        cnt = lambda g: g.get("count") or len(g.get("sessions", []))
        top, tie = top_with_ties(gaps, cnt, 3)
        out["top_knowledge_gaps"] = {"items": [{"gap_id": g.get("gap_id"), "count": cnt(g)} for g in top], "tie_at_cutoff": tie}
    fb = rjson(ws, "feedback.json")
    if fb:
        fr = [i for i in fb.get("items", []) if i.get("type") == "feature_request"]
        score = lambda i: (i.get("count") or len(i.get("sessions", []))) * STRENGTH.get(i.get("strength"), 1)
        top, tie = top_with_ties(fr, score, 3)
        out["top_feature_requests"] = {"items": [{"id": i.get("id"), "title": i.get("title"), "count": i.get("count"),
                                                  "strength": i.get("strength"), "rank_score": score(i)} for i in top],
                                       "tie_at_cutoff": tie}
    pig = rjson(ws, "product-info-gaps.json")
    if pig:
        gaps = pig.get("gaps", pig if isinstance(pig, list) else [])
        top, tie = top_with_ties(gaps, lambda g: g.get("count") or len(g.get("sessions", [])), 1)
        out["top_product_info_gap"] = {"items": [{k: g.get(k) for k in ("product", "attribute", "count")} for g in top], "tie_at_cutoff": tie}
    con = rjson(ws, "contradictions.json")
    if con:
        items = con.get("contradictions", con if isinstance(con, list) else [])
        out["contradictions"] = [{k: c.get(k) for k in ("id", "subject", "attribute", "confidence", "likely_truth")} for c in items]
    return out


def check(ws, files):
    ids = {s["session_id"] for s in load_sessions(ws)}
    problems = []
    for f in files:
        text = open(f, encoding="utf-8").read()
        if f.endswith(".json") or f.endswith(".jsonl"):
            try:
                docs = [json.loads(l) for l in text.splitlines() if l.strip()] if f.endswith(".jsonl") else [json.loads(text)]
            except json.JSONDecodeError as e:
                problems.append(f"{f}: invalid JSON ({e})")
                docs = []
            cited = set()

            def walk(x, key=None):
                if isinstance(x, dict):
                    for k, v in x.items():
                        walk(v, k)
                elif isinstance(x, list):
                    for v in x:
                        walk(v, key)
                elif isinstance(x, str) and key in ("session_id", "sessions", "session_ids", "related_sessions") \
                        and re.match(r"^co[\w-]+(#\d+)?$", x):
                    cited.add(x)
            for d in docs:
                walk(d)
                if isinstance(d, dict) and isinstance(d.get("assignments"), dict):
                    cited.update(k for k in d["assignments"] if k.startswith("co"))
            bad = sorted(c for c in cited if c not in ids)
            if bad:
                problems.append(f"{f}: {len(bad)} unknown session ids (use session_id exactly, e.g. coAbc#0): {bad[:5]}")
        if re.search(r"\[[A-Z_]{3,}\]", text):
            problems.append(f"{f}: contains [PLACEHOLDER] tokens")
    for p in problems:
        print("PROBLEM", p)
    r = subprocess.run([sys.executable, os.path.join(HERE, "leakcheck.py"), ws, *files], capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip())
    sys.exit(1 if problems or r.returncode else 0)


def main():
    cmd, ws = sys.argv[1], sys.argv[2]
    if cmd == "cx-summary":
        print(json.dumps(cx_summary(ws), ensure_ascii=False, indent=1))
    elif cmd == "topic-stats":
        print(topic_stats(ws))
    elif cmd == "pulse-metrics":
        print(json.dumps(pulse_metrics(ws), ensure_ascii=False, indent=1))
    elif cmd == "check":
        check(ws, sys.argv[3:])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
