#!/usr/bin/env bash
# Weekly Smartsupp insights run on pi (Homebrew build), end to end:
#   1. fetch    — with the smartsupp CLI installed and a token configured, the script fetches itself
#                 (+fetch and statistics.json, no model tokens); otherwise a pi session with
#                 read-only Smartsupp MCP tools writes raw/, contacts/, manifest.json
#   2. prepare  — normalize.py → redact.py → digest.py (deterministic)
#   3. analyse  — one pi session runs all 7 skills; get_statistics is allowed from Smartsupp only when statistics.json was not pre-fetched
#   4. check    — insights.py check over every output; usage + cost summary from pi's JSON events
#
#   weekly-pi.sh [--from YYYY-MM-DD --to YYYY-MM-DD] [--out DIR] [--kb DIR]
#                [--fetch-model M] [--model M] [--thinking LEVEL] [--from-step fetch|analyse]
#
# Default window: last full ISO week (Mon–Sun). Default models: fetch on
# openai-codex/gpt-6.1-sol, analysis on anthropic/claude-opus-5-5 (28/28 in the benchmark).
# --from-step analyse reuses an already fetched and prepared workspace.
# Env: PI_BIN = path to the pi binary (default /opt/homebrew/bin/pi).
# Needs: `pi mcp add smartsupp --url https://mcp.smartsupp.com/mcp` + `pi mcp login smartsupp`,
# and pi logged in to the chosen providers. Nothing is posted anywhere; the weekly post is
# written to the workspace for review. Exit code 1 when a session fails or the check fails.
HERE="$(cd "$(dirname "$0")" && pwd)"
SKILLS="$(cd "$HERE/../skills" && pwd)"
S="$SKILLS/smartsupp-conversations/scripts"
PI="${PI_BIN:-/opt/homebrew/bin/pi}"   # PI_BIN overrides the pi path (used by tests)
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

PI_ROUTE=""   # every pi session pins SMARTSUPP_ROUTE=mcp; the token variable is always removed from pi sessions
run_pi() {  # name model tools prompt-file
  ( cd "$JOB" && unset SMARTSUPP_API_TOKEN && { [ -z "$PI_ROUTE" ] || export SMARTSUPP_ROUTE="$PI_ROUTE"; } && PI_TELEMETRY=0 "$PI" --mode json --no-session --approve --model "$2" --thinking "$THINK" \
      --tools "$3" "$(render "$4")" > "logs/$1.pi.jsonl" 2> "logs/$1.pi.err" )
  echo "$1: exit $?"
  local err; err=$(session_error "$JOB/logs/$1.pi.jsonl")
  if [ -n "$err" ]; then echo "$1 FAILED: $err"; exit 1; fi
}

FETCH_ROUTE="reused workspace"
if [ "$STEP" = fetch ]; then
  # never delete or overwrite earlier statistics: move them aside (a stale file would hide get_statistics)
  [ -f "$WS/statistics.json" ] && mv -n "$WS/statistics.json" "$WS/statistics.$(date +%Y%m%dT%H%M%S).json"
  CLI_OK=0
  if command -v smartsupp >/dev/null; then
    smartsupp auth check --scopes conversations:read,contacts:read,tags:read,statistics:read >/dev/null 2>&1 && CLI_OK=1 \
      || echo "smartsupp CLI found but auth check failed (exit $?): using the MCP route"
  fi
  if [ "$CLI_OK" = 1 ]; then
    # CLI route: the script fetches itself (no model tokens, the token never enters a pi session)
    FETCH_ROUTE=cli
    smartsupp conversations +fetch --from "$FROM" --to "$TO" --ws "$WS" \
      || { echo "fetch FAILED: smartsupp conversations +fetch exited non-zero"; exit 1; }
    smartsupp statistics query --metric new_conversation --metric closed_conversation \
      --metric first_response_time --metric conversation_ratings \
      --from "$FROM" --to "$TO" --out "$WS/statistics.json" \
      || { echo "fetch FAILED: smartsupp statistics query exited non-zero"; exit 1; }
  else
    FETCH_ROUTE=mcp
    PI_ROUTE=mcp   # the skill inside the session must not pick the CLI itself
    run_pi fetch "$FETCH_MODEL" "read,write,bash,codemode,$READ_TOOLS" "$HERE/prompts/fetch.md"
    n=$(ls "$WS/raw" 2>/dev/null | wc -l | tr -d ' ')
    [ "$n" -gt 0 ] || { echo "no conversations fetched — see $JOB/logs/fetch.pi.jsonl"; exit 1; }
  fi
  python3 "$S/normalize.py" "$WS/raw" "$WS/sessions.jsonl" || exit 1
  python3 "$S/redact.py" "$WS/sessions.jsonl" "$WS/sessions.redacted.jsonl" --contacts "$WS/contacts" \
    $([ -d "$WS/kb" ] && echo --kb "$WS/kb") || exit 1
  python3 "$S/digest.py" "$WS" || exit 1
fi

ANALYSE_TOOLS="read,write,edit,bash,codemode"
[ -f "$WS/statistics.json" ] || ANALYSE_TOOLS="$ANALYSE_TOOLS,mcp__smartsupp__get_statistics"
PI_ROUTE=mcp   # analyse never uses the CLI
run_pi analyse "$MODEL" "$ANALYSE_TOOLS" "$HERE/prompts/analyse.md"

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
echo "fetch: $FETCH_ROUTE"
echo "outputs: $WS/results  (weekly post: $WS/results/weekly-pulse.md)"
