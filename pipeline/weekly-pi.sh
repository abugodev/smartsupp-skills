#!/usr/bin/env bash
# Weekly Smartsupp insights run on pi (Homebrew build), end to end:
#   1. fetch    — pi session with read-only Smartsupp MCP tools writes raw/, contacts/, manifest.json
#   2. prepare  — normalize.py → redact.py → digest.py (deterministic)
#   3. analyse  — one pi session runs all 7 skills; only get_statistics is allowed from Smartsupp
#   4. check    — insights.py check over every output; usage + cost summary from pi's JSON events
#
#   weekly-pi.sh [--from YYYY-MM-DD --to YYYY-MM-DD] [--out DIR] [--kb DIR]
#                [--fetch-model M] [--model M] [--thinking LEVEL] [--from-step fetch|analyse]
#
# Default window: last full ISO week (Mon–Sun). Default models: fetch on
# openai-codex/gpt-6.1-sol, analysis on anthropic/claude-opus-5-5 (28/28 in the benchmark).
# --from-step analyse reuses an already fetched and prepared workspace.
# Needs: `pi mcp add smartsupp --url https://mcp.smartsupp.com/mcp` + `pi mcp login smartsupp`,
# and pi logged in to the chosen providers. Nothing is posted anywhere; the weekly post is
# written to the workspace for review. Exit code 1 when a session fails or the check fails.
HERE="$(cd "$(dirname "$0")" && pwd)"
SKILLS="$(cd "$HERE/../skills" && pwd)"
S="$SKILLS/smartsupp-conversations/scripts"
PI=/opt/homebrew/bin/pi
FROM=""; TO=""; OUT="$PWD/smartsupp-insights"; KB=""; STEP="fetch"
FETCH_MODEL="openai-codex/gpt-6.1-sol"; MODEL="anthropic/claude-opus-5-5"; THINK="medium"
while [ $# -gt 0 ]; do
  case "$1" in
    --from) FROM="$2"; shift 2 ;; --to) TO="$2"; shift 2 ;; --out) OUT="$2"; shift 2 ;;
    --kb) KB="$2"; shift 2 ;; --fetch-model) FETCH_MODEL="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;; --thinking) THINK="$2"; shift 2 ;;
    --from-step) STEP="$2"; shift 2 ;;
    *) echo "unknown option $1"; exit 2 ;;
  esac
done
if [ -z "$FROM" ]; then
  read -r FROM TO WID < <(python3 -c '
import datetime as d
t = d.date.today(); mon = t - d.timedelta(days=t.weekday() + 7); sun = mon + d.timedelta(days=6)
y, w, _ = mon.isocalendar(); print(mon, sun, f"{y}-W{w:02d}")')
else
  WID=$(python3 -c '
import datetime as d, sys
a, b = d.date.fromisoformat(sys.argv[1]), d.date.fromisoformat(sys.argv[2])
y, w, wd = a.isocalendar()
print(f"{y}-W{w:02d}" if wd == 1 and (b - a).days == 6 else f"{a}_{b}")' "$FROM" "$TO")
fi
JOB="$OUT/$WID"; WS="$JOB/ws"
mkdir -p "$WS/results" "$JOB/logs" "$JOB/.agents"
rm -rf "$JOB/.agents/skills"; cp -R "$SKILLS" "$JOB/.agents/skills"
[ -n "$KB" ] && { mkdir -p "$WS/kb"; cp "$KB"/*.md "$KB"/*.txt "$WS/kb/" 2>/dev/null; }
echo "window $FROM – $TO → $WS (from step: $STEP)"

READ_TOOLS="mcp__smartsupp__search_conversations,mcp__smartsupp__get_conversation,mcp__smartsupp__list_messages,mcp__smartsupp__list_tags,mcp__smartsupp__get_contact"

render() { sed "s#{WS}#$WS#g; s#{SKILLS}#$JOB/.agents/skills#g; s#{FROM}#$FROM#g; s#{TO}#$TO#g" "$1"; }

session_error() {  # prints the error of a session whose last assistant message failed
  python3 -c '
import json, sys
last = None
for line in open(sys.argv[1], encoding="utf-8", errors="replace"):
    if "\"message_end\"" in line:
        m = json.loads(line).get("message") or {}
        if m.get("role") == "assistant":
            last = m
if last is None:
    print("no assistant response")
elif last.get("stopReason") == "error":
    print((last.get("errorMessage") or "error")[:300])' "$1"
}

run_pi() {  # name model tools prompt-file
  ( cd "$JOB" && PI_TELEMETRY=0 "$PI" --mode json --no-session --approve --model "$2" --thinking "$THINK" \
      --tools "$3" "$(render "$4")" > "logs/$1.pi.jsonl" 2> "logs/$1.pi.err" )
  echo "$1: exit $?"
  local err; err=$(session_error "$JOB/logs/$1.pi.jsonl")
  if [ -n "$err" ]; then echo "$1 FAILED: $err"; exit 1; fi
}

if [ "$STEP" = fetch ]; then
  run_pi fetch "$FETCH_MODEL" "read,write,bash,codemode,$READ_TOOLS" "$HERE/prompts/fetch.md"
  n=$(ls "$WS/raw" 2>/dev/null | wc -l | tr -d ' ')
  [ "$n" -gt 0 ] || { echo "no conversations fetched — see $JOB/logs/fetch.pi.jsonl"; exit 1; }
  python3 "$S/normalize.py" "$WS/raw" "$WS/sessions.jsonl" || exit 1
  python3 "$S/redact.py" "$WS/sessions.jsonl" "$WS/sessions.redacted.jsonl" --contacts "$WS/contacts" \
    $([ -d "$WS/kb" ] && echo --kb "$WS/kb") || exit 1
  python3 "$S/digest.py" "$WS" || exit 1
fi

run_pi analyse "$MODEL" "read,write,edit,bash,codemode,mcp__smartsupp__get_statistics" "$HERE/prompts/analyse.md"

files=$(find "$WS/results" -type f \( -name '*.json' -o -name '*.jsonl' -o -name '*.md' \))
[ -n "$files" ] || { echo "check: FAILED — no outputs in $WS/results"; exit 1; }
# shellcheck disable=SC2086
python3 "$S/insights.py" check "$WS" $files && echo "check: ok" || { echo "check: PROBLEMS — do not publish"; exit 1; }

python3 -c '
import glob, json, sys
for f in sorted(glob.glob(sys.argv[1] + "/*.pi.jsonl")):
    t = {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}; cost = 0.0; turns = 0; model = None
    for line in open(f, encoding="utf-8", errors="replace"):
        if "\"message_end\"" not in line:
            continue
        m = json.loads(line).get("message") or {}
        if m.get("role") == "assistant" and m.get("usage"):
            turns += 1; model = m.get("model") or model
            for k in t:
                t[k] += m["usage"].get(k, 0) or 0
            cost += (m["usage"].get("cost") or {}).get("total") or 0
    name = f.rsplit("/", 1)[-1]
    print(f"{name}: {model}, {turns} turns, tokens {t}, provider-reported cost ${cost:.2f}")' "$JOB/logs"
echo "outputs: $WS/results  (weekly post: $WS/results/weekly-pulse.md)"
