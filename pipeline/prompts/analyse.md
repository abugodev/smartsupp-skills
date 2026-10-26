This is the weekly Smartsupp insights run for {FROM} – {TO}. Workspace: `{WS}`.
Only read from Smartsupp; never send, close, tag or change anything there. Do not post the weekly pulse anywhere — write it to the workspace only.

Run the seven Smartsupp insight skills below **in this one session, in this order**. Finish each skill (outputs written, leakcheck passed) before starting the next; later skills read earlier results. Reuse what you already read and wrote earlier in this session instead of re-reading it. At the end, report per skill what you produced and anything ambiguous.

### Step 1: contradiction-finder

Run the `contradiction-finder` skill ({SKILLS}/contradiction-finder/SKILL.md) on the
Smartsupp workspace {WS}. The data for the window {FROM} – {TO} is already fetched, sessionised and redacted (steps
1–4 of the `smartsupp-conversations` skill are done — read
{SKILLS}/smartsupp-conversations/SKILL.md for the shared conventions). The AI agent's
knowledge export is in {WS}/kb/. Follow the SKILL.md exactly and write the outputs to
{WS}/results/. Read only the skill files and the workspace. Do not call Smartsupp tools. When done, report what you produced and anything in the SKILL.md that was
ambiguous.

### Step 2: cx-score

Run the `cx-score` skill ({SKILLS}/cx-score/SKILL.md) on the Smartsupp workspace {WS}.
The data for the window {FROM} – {TO} is already fetched, sessionised and redacted (read
{SKILLS}/smartsupp-conversations/SKILL.md for the shared conventions).
{WS}/results/contradictions.json is available. Follow the SKILL.md exactly and write the
outputs to {WS}/results/. Read only the skill files and the workspace. Do not call Smartsupp tools. Report what you produced and anything ambiguous.

### Step 3: topic-clusters

Run the `topic-clusters` skill ({SKILLS}/topic-clusters/SKILL.md) on the Smartsupp
workspace {WS}. The data for the window {FROM} – {TO} is already fetched, sessionised and redacted (read
{SKILLS}/smartsupp-conversations/SKILL.md for the shared conventions). There is no
previous taxonomy — build one and save it as {WS}/taxonomy.json. {WS}/results/cx-score.jsonl
is available. Follow the SKILL.md exactly and write the outputs to {WS}/results/. Read
only the skill files and the workspace. Do not call Smartsupp tools. Report what
you produced and anything ambiguous.

### Step 4: knowledge-gaps

Run the `knowledge-gaps` skill ({SKILLS}/knowledge-gaps/SKILL.md) on the Smartsupp
workspace {WS}. The data for the window {FROM} – {TO} is already fetched, sessionised and redacted (read
{SKILLS}/smartsupp-conversations/SKILL.md — you need its personal-data gate, conventions
and scripts/leakcheck.py). The AI agent's knowledge export is in {WS}/kb/. Follow the
SKILL.md exactly and write the outputs to {WS}/results/. Read only the skill files and
the workspace. Do not call Smartsupp tools. Report what you produced, the
leakcheck result and anything ambiguous.

### Step 5: feedback-drafts

Run the `feedback-drafts` skill ({SKILLS}/feedback-drafts/SKILL.md) on the Smartsupp
workspace {WS}. The data for the window {FROM} – {TO} is already fetched, sessionised and redacted (read
{SKILLS}/smartsupp-conversations/SKILL.md for the personal-data gate, conventions and
scripts/leakcheck.py). Follow the SKILL.md exactly and write the outputs to
{WS}/results/. Do not send anything anywhere. Read only the skill files and the
workspace. Do not call Smartsupp tools. Report what you produced, the leakcheck
result and anything ambiguous.

### Step 6: product-info-gaps

Run the `product-info-gaps` skill ({SKILLS}/product-info-gaps/SKILL.md) on the Smartsupp
workspace {WS}. The data for the window {FROM} – {TO} is already fetched, sessionised and redacted (read
{SKILLS}/smartsupp-conversations/SKILL.md for the personal-data gate, conventions and
scripts/leakcheck.py). Follow the SKILL.md exactly and write the outputs to
{WS}/results/. Read only the skill files and the workspace. Do not call Smartsupp tools. Report what you produced, the leakcheck result and anything ambiguous.

### Step 7: weekly-pulse

Run the `weekly-pulse` skill ({SKILLS}/weekly-pulse/SKILL.md) on the Smartsupp workspace
{WS}. The results of all other skills are already in {WS}/results/ — do not re-run them.
Read {SKILLS}/smartsupp-conversations/SKILL.md for the conventions, personal-data gate
and scripts/leakcheck.py. There is no previous week's workspace. Do not call any
Smartsupp tools except `get_statistics` (call it through codemode as `tools.mcp__smartsupp__get_statistics` for the same window). Do not post anything
anywhere. Write {WS}/results/weekly-pulse.md and weekly-pulse.json. Read only the skill
files and the workspace. Report the post, its length, the leakcheck result and anything
ambiguous.
