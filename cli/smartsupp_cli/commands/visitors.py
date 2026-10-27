from ..errors import UsageError
from ..ops import Op, Param

_TEXT = Param("text", "--text", help="message text")
_ATTACHMENTS = Param("attachments", "--attachments", type="json",
                     help="JSON array of attachments (max 5): type file|image, url, ...")
_DISABLE_INPUT = Param("disable_input", "--disable-input", type="boolean",
                       help="true to disable the visitor's input after this message")


def _message(args) -> dict:
    """Build a visitor_message_request from the flags that were given."""
    msg = {}  # type: dict
    if args.b_text is not None:
        msg["content"] = {"type": "text", "text": args.b_text}
    if args.b_attachments is not None:
        if not isinstance(args.b_attachments, list):
            raise UsageError("--attachments must be a JSON array")
        msg["attachments"] = args.b_attachments
    if args.b_disable_input is not None:
        msg["disable_input"] = args.b_disable_input
    return msg


def _merged(args, base) -> dict:
    """The --json message with the flags laid over it (flags win per key); needs content or attachments."""
    merged = dict(base) if base is not None else {}
    merged.update(_message(args))
    if not merged.get("content") and not merged.get("attachments"):
        raise UsageError("give --text or --attachments (or supply them via --json)")
    return merged


def _send_body(args) -> dict:
    return _merged(args, getattr(args, "json_obj", {}))


def _start_body(args) -> dict:
    json_obj = getattr(args, "json_obj", {})
    if "message" in json_obj and not isinstance(json_obj["message"], dict):
        raise UsageError("--json message must be a JSON object")
    return {"message": _merged(args, json_obj.get("message"))}


_MESSAGE_PARAMS = [_TEXT, _ATTACHMENTS, _DISABLE_INPUT]

OPS = [
    Op("visitors", "get", "GET", "/visitors/{id}", False, "visitors:read, contacts:read", "Get a visitor",
       path_params=["id"]),
    Op("visitors", "paths", "GET", "/visitors/{id}/paths", False, "visitors:read",
       "Get a visitor's page paths", path_params=["id"]),
    Op("visitors", "update", "PATCH", "/visitors/{id}", True, "visitors:write", "Update a visitor",
       path_params=["id"],
       body=[
           Param("group", "--group", help="visitor group"),
           Param("email", "--email", help="visitor email, <email>"),
           Param("name", "--name", help="visitor name"),
           Param("phone", "--phone", help="visitor phone number"),
           Param("variables", "--variables", type="json", help="JSON object of custom variables"),
       ]),
    Op("visitors", "start-conversation", "POST", "/visitors/{id}/conversations", True,
       "visitors:conversations:write", "Start a conversation as the visitor",
       path_params=["id"], body=list(_MESSAGE_PARAMS), build_body=_start_body),
    Op("visitors", "send-message", "POST", "/visitors/{id}/conversations/{conversation_id}/messages",
       True, "visitors:conversations:write", "Send a message to a conversation as the visitor",
       path_params=["id", "conversation_id"], body=list(_MESSAGE_PARAMS), build_body=_send_body),
    Op("visitors", "open-conversation", "POST", "/visitors/{id}/conversations/{conversation_id}/open",
       True, "visitors:conversations:write", "Open a conversation and notify agents",
       path_params=["id", "conversation_id"]),
    Op("visitors", "typing", "POST", "/visitors/{id}/conversations/{conversation_id}/typing",
       True, "conversations:write", "Set the visitor typing indicator",
       path_params=["id", "conversation_id"],
       body=[Param("active", "--active", type="boolean", required=True, help="true or false")]),
]
