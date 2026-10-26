Fetch the Smartsupp conversations for the window {FROM} – {TO} (closed conversations whose
`finished_at` falls in the window) into the workspace {WS}, following step 1 of
{SKILLS}/smartsupp-conversations/SKILL.md exactly (read it and its
references/smartsupp-data-model.md first).

- Use codemode scripts to call the Smartsupp tools (`tools.mcp__smartsupp__search_conversations`,
  `get_conversation`, `list_messages`, `list_tags`, `get_contact`): page through every result
  and write the compact files in bulk from the script, not one tool call per conversation.
- Write `{WS}/raw/<conversation_id>.json`, `{WS}/contacts/<contact_id>.json` and
  `{WS}/manifest.json` (window, counts, skipped conversations and why).
- Only read from Smartsupp. Never send messages, close, open, assign, tag or change anything.
- Do not analyse the chats and do not print message contents or contact details in your
  reply. Report only counts: conversations found, fetched, skipped, contacts written.
