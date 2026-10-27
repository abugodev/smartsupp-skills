from pathlib import Path

from ..client import Client
from ..config import load_config
from ..errors import CliError, UsageError
from ..helpers import fetch
from ..ops import Op, Param
from ..output import emit
from ..search import build_search_body, parse_range


def _search_body(args) -> dict:
    extra = []
    if args.b_finished is not None:
        extra.append({"field": "finished_at", "value": parse_range(args.b_finished, "--finished")})
    if args.b_created is not None:
        extra.append({"field": "created_at", "value": parse_range(args.b_created, "--created")})
    json_tz = getattr(args, "json_obj", {}).get("timezone")
    if isinstance(json_tz, str) and not json_tz.strip():
        raise UsageError("timezone must not be empty")
    base = getattr(args, "json_obj", {}).get("query")  # --json clauses; the flags append to them
    if base is not None and not (isinstance(base, list) and all(isinstance(c, dict) for c in base)):
        raise UsageError("--json query must be an array of clause objects")
    body = build_search_body(
        args.b_where or [], args.b_not or [], args.b_any or [], args.b_sort or [],
        args.b_size, args.b_timezone, args.b_after, extra_clauses=extra, base_clauses=base)
    if "timezone" not in body and json_tz is None and "timezone" in getattr(args, "json_obj", {}):
        body["timezone"] = "UTC"  # an explicit "timezone": null means the default, not "no timezone"
    return body


def _reply_body(args) -> dict:
    body = {}  # type: dict
    for name in ("sub_type", "agent_id", "contact_id", "bot_id", "bot_name", "virtual_agent",
                 "attachments", "ext_id"):
        value = getattr(args, "b_" + name)
        if name == "virtual_agent" and value is not None and not isinstance(value, dict):
            raise UsageError("--virtual-agent must be a JSON object")
        if value is not None:
            body[name] = value
    if args.b_text is not None or args.b_html is not None:
        body["content"] = {"type": "text"}
        if args.b_text is not None:
            body["content"]["text"] = args.b_text
        if args.b_html is not None:
            body["content"]["html"] = args.b_html
    return body


_SEARCH_PARAMS = [
    Param("where", "--where", repeat=True, help="FIELD=VALUE clause (JSON values allowed), repeatable"),
    Param("not", "--not", repeat=True, help="FIELD=VALUE clause that must not match, repeatable"),
    Param("any", "--any", repeat=True, help="FIELD=V1,V2 clause matching any value, repeatable"),
    Param("sort", "--sort", repeat=True, help="FIELD:asc|desc, at most 3"),
    Param("size", "--size", type="integer", help="page size"),
    Param("timezone", "--timezone", help="timezone for dates (default UTC)"),
    Param("after", "--after", help="cursor as a JSON array, passed verbatim"),
    Param("finished", "--finished", help="FROM..TO (YYYY-MM-DD each) on finished_at, UTC days"),
    Param("created", "--created", help="FROM..TO (YYYY-MM-DD each) on created_at, UTC days"),
]

_REPLY_PARAMS = [
    Param("sub_type", "--sub-type", choices=["agent", "contact", "bot"], help="sender kind (default agent)"),
    Param("agent_id", "--agent-id", help="agent id, required for sub-type agent"),
    Param("contact_id", "--contact-id", help="contact id, required for sub-type contact"),
    Param("bot_id", "--bot-id", help="bot id, required for sub-type bot"),
    Param("bot_name", "--bot-name", help="bot display name"),
    Param("virtual_agent", "--virtual-agent", type="json",
          help="JSON virtual agent identity (sub-type agent or bot)"),
    Param("text", "--text", help="plain text message"),
    Param("html", "--html", help="HTML message (a and br only); needs a text or an html"),
    Param("attachments", "--attachments", type="json", help="JSON array of attachments (max 5)"),
    Param("ext_id", "--ext-id", help="your custom message id"),
]

_C = "/conversations/{id}"

OPS = [
    Op("conversations", "get", "GET", _C, False, "conversations:read", "Get a conversation",
       path_params=["id"],
       query=[Param("messages", "--messages", type="flag", help="include messages"),
              Param("paths", "--paths", type="flag", help="include visitor paths"),
              Param("statistics", "--statistics", type="flag", help="include statistics")]),
    Op("conversations", "find", "GET", "/conversations/find", False, "conversations:read",
       "Find a conversation by its custom id",
       query=[Param("ext_id", "--ext-id", required=True, help="custom conversation id")]),
    Op("conversations", "search", "POST", "/conversations/search", False, "conversations:read",
       "Search conversations", body=list(_SEARCH_PARAMS), build_body=_search_body, paged=True,
       body_defaults={"timezone": "UTC"},
       # the API returns a cursor only for a sorted search
       page_all_defaults={"sort": [{"created_at": "asc"}]}),
    Op("conversations", "messages", "GET", _C + "/messages", False, "conversations:read",
       "List messages of a conversation", path_params=["id"], paged=True,
       query=[Param("size", "--size", type="integer", help="page size"),
              Param("after", "--after", type="integer", help="cursor"),
              Param("sort", "--sort", choices=["asc", "desc", "ASC", "DESC"], help="asc or desc")]),
    Op("conversations", "tags", "GET", _C + "/tags", False, "conversations:read",
       "List tags of a conversation", path_params=["id"]),
    Op("conversations", "create", "POST", "/conversations", True, "conversations:create",
       "Create a conversation", body=[
           Param("contact_id", "--contact-id", required=True, help="contact id (ct...)"),
           Param("assigned_ids", "--assigned-ids", type="json", help="JSON array of agent ids"),
           Param("group_id", "--group-id", help="route to this group"),
           Param("ext_id", "--ext-id", help="your custom conversation id"),
           Param("variables", "--variables", type="json", help="JSON object of variables"),
           Param("tags", "--tags", type="json", help="JSON array of tag ids"),
           Param("text", "--text", help="plain text of the first message"),
           Param("html", "--html", help="HTML of the first message (a and br only)"),
           Param("messages", "--messages", type="json", help="JSON array of messages to import"),
       ]),
    Op("conversations", "update", "PATCH", _C, True, "conversations:write", "Update a conversation",
       path_params=["id"], body=[
           Param("group_id", "--group-id", help="group id"),
           Param("variables", "--variables", type="json", help="JSON object of variables"),
           Param("virtual_agent", "--virtual-agent", type="json", help="JSON virtual agent identity"),
       ]),
    Op("conversations", "assign", "PATCH", _C + "/assign", True, "conversations:write",
       "Assign an agent to a conversation", path_params=["id"], body=[
           Param("agent_id", "--agent-id", required=True, help="agent performing the action"),
           Param("assignee_id", "--assignee-id", required=True, help="agent being assigned"),
       ]),
    Op("conversations", "unassign", "PATCH", _C + "/unassign", True, "conversations:write",
       "Unassign an agent from a conversation", path_params=["id"], body=[
           Param("agent_id", "--agent-id", required=True, help="agent performing the action"),
           Param("unassignee_id", "--unassignee-id", required=True, help="agent being unassigned"),
       ]),
    Op("conversations", "open", "PATCH", _C + "/open", True, "conversations:write",
       "Open a conversation", path_params=["id"]),
    Op("conversations", "close", "PATCH", _C + "/close", True, "conversations:write",
       "Close a conversation", path_params=["id"]),
    Op("conversations", "reply", "POST", _C + "/messages", True, "conversations:write",
       "Post a message to a conversation", path_params=["id"], body=list(_REPLY_PARAMS),
       build_body=_reply_body),
    Op("conversations", "rate", "PATCH", _C + "/rate", True, "conversations:write",
       "Rate a conversation", path_params=["id"], body=[
           Param("value", "--value", type="integer", required=True, choices=[1, 3, 5],
                 help="rating 1, 3 or 5"),
           Param("text", "--text", help="rating comment (max 500 chars)"),
       ]),
    Op("conversations", "trigger-rating", "PATCH", _C + "/trigger-rating", True,
       "conversations:write", "Ask the visitor to rate the conversation", path_params=["id"]),
    Op("conversations", "typing", "POST", _C + "/typing", True, "conversations:write",
       "Set the typing indicator", path_params=["id"],
       body=[Param("active", "--active", type="boolean", required=True, help="true or false")]),
    Op("conversations", "tag", "POST", _C + "/tags", True, "conversations:write",
       "Add a tag to a conversation", path_params=["id"],
       body=[Param("id", "--id", required=True, help="tag id (tg...)")]),
    Op("conversations", "untag", "DELETE", _C + "/tags/{tag_id}", True, "conversations:write",
       "Remove a tag from a conversation", path_params=["id", "tag_id"]),
    # Scope is read, but it emails the transcript, so it is a write for the gate.
    Op("conversations", "transcript", "POST", _C + "/transcript", True, "conversations:read",
       "Email a conversation transcript", path_params=["id"], body=[
           Param("email", "--email", required=True, help="recipient, <email>"),
           Param("lang", "--lang", required=True, help="transcript language, e.g. en"),
       ]),
]


def _fetch_handler(args) -> int:
    if not args.timezone.strip():
        raise UsageError("--timezone must not be empty")
    if args.workers < 1:
        raise UsageError("--workers must be at least 1")
    exclude = fetch.DEFAULT_EXCLUDE if args.exclude_tag is None else args.exclude_tag
    client = Client(load_config())
    try:
        manifest = fetch.run_fetch(client, Path(args.ws), args.date_from, args.date_to, status=args.status,
                                   exclude_tags=exclude, timezone=args.timezone, workers=args.workers)
    except OSError as e:  # local disk trouble: the workspace is left without partial files
        raise CliError("cannot write the workspace: %s" % (e.strerror or type(e).__name__))
    emit(manifest["counts"])  # counts only: never contact fields or message text
    return 0


def register_helpers(subparsers) -> None:
    sp = subparsers.add_parser(
        "+fetch", help="fetch a window of conversations into a smartsupp-conversations workspace",
        description="Write raw/<id>.json, contacts/<id>.json and manifest.json for the window "
                    "(the smartsupp-conversations fetch step). Prints counts only. "
                    "Scopes: conversations:read, contacts:read, tags:read.")
    sp.add_argument("--from", dest="date_from", required=True, metavar="YYYY-MM-DD", help="first day")
    sp.add_argument("--to", dest="date_to", required=True, metavar="YYYY-MM-DD", help="last day")
    sp.add_argument("--ws", required=True, metavar="DIR", help="workspace directory")
    sp.add_argument("--status", choices=fetch.STATUSES, default="closed",
                    help="closed (default, by finished_at), open (by created_at) or all")
    sp.add_argument("--exclude-tag", action="append", default=None, metavar="NAME",
                    help="skip conversations with this tag name, repeatable (default: %s)"
                    % ", ".join(fetch.DEFAULT_EXCLUDE))
    sp.add_argument("--timezone", default="UTC", help="timezone of the day window (default UTC)")
    sp.add_argument("--workers", type=int, default=4, metavar="N", help="parallel requests (default 4)")
    sp.set_defaults(handler=_fetch_handler)
