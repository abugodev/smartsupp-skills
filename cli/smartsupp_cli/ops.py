"""Declarative command framework: an Op describes one API call; register/run turn it into a CLI."""
import argparse
import copy
import json
from urllib.parse import quote
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .client import Client
from .errors import UsageError
from .output import atomic_writer, emit, emit_line

PARAM_TYPES = ("string", "integer", "number", "boolean", "json", "flag")


@dataclass
class Param:
    name: str
    flag: str
    type: str = "string"
    required: bool = False
    help: str = ""
    choices: Optional[list] = None
    repeat: bool = False
    default: Any = None  # used when the flag is not given


@dataclass
class Op:
    resource: str
    name: str
    method: str
    path: str
    write: bool
    scope: str
    help: str
    path_params: List[str] = field(default_factory=list)
    query: List[Param] = field(default_factory=list)
    body: List[Param] = field(default_factory=list)
    paged: bool = False
    build_body: Optional[Callable[[argparse.Namespace], dict]] = None
    # the body must carry at least one field (the API rejects an empty one)
    body_required: bool = False
    # applied only for keys neither --json nor a flag set (an explicit JSON null is kept)
    body_defaults: Dict[str, Any] = field(default_factory=dict)
    # like body_defaults, but only when the request is paged with --page-all
    page_all_defaults: Dict[str, Any] = field(default_factory=dict)

    @property
    def scopes(self) -> List[str]:
        """Token scopes of the endpoint: `scope` is a comma-separated list, order kept."""
        return [s.strip() for s in (self.scope or "").split(",") if s.strip()]

    @property
    def has_body(self) -> bool:
        return bool(self.body) or self.build_body is not None


def _json_value(text: str) -> Any:
    try:
        return json.loads(text)
    except ValueError as e:
        raise argparse.ArgumentTypeError("not valid JSON: %s" % e)


def _bool_value(text: str) -> bool:
    low = text.lower()
    if low in ("true", "1", "yes"):
        return True
    if low in ("false", "0", "no"):
        return False
    raise argparse.ArgumentTypeError("expected true or false, got %r" % text)


_CONVERTERS = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": _bool_value,
    "json": _json_value,
}  # "flag" has no converter: it is a store_const switch


def _dest(kind: str, param: Param) -> str:
    return "%s_%s" % (kind, param.name)


def _add_param(parser: argparse.ArgumentParser, kind: str, param: Param) -> None:
    if param.type not in PARAM_TYPES:
        raise ValueError("unknown param type %r" % param.type)
    if param.type == "flag":  # bare switch: True when given, else unset
        parser.add_argument(param.flag, dest=_dest(kind, param), action="store_const", const=True,
                            default=None, help=param.help or None)
        return
    kwargs = {"dest": _dest(kind, param), "default": param.default, "type": _CONVERTERS[param.type],
              "help": param.help or None, "metavar": param.type.upper()}
    if param.choices:
        kwargs["choices"] = param.choices
    if param.repeat:
        kwargs["action"] = "append"
    parser.add_argument(param.flag, **kwargs)


def register(subparsers, ops: List[Op]) -> Dict[str, Any]:
    """Add one subparser per resource and one sub-subparser per op; return the per-resource subparsers."""
    resources = {}  # type: Dict[str, Any]
    for op in ops:
        if op.resource not in resources:
            rp = subparsers.add_parser(op.resource, help="%s commands" % op.resource)
            resources[op.resource] = rp.add_subparsers(
                dest="%s_command" % op.resource, parser_class=type(rp), metavar="<command>"
            )
        sp = resources[op.resource].add_parser(
            op.name,
            help=op.help,
            description="%s\n\nEndpoint: %s %s (%s, scope: %s)"
            % (op.help, op.method, op.path, "write" if op.write else "read", ", ".join(op.scopes) or "none"),
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        for pname in op.path_params:
            sp.add_argument("pp_" + pname, metavar=pname.upper())
        for param in op.query:
            _add_param(sp, "q", param)
        for param in op.body:
            _add_param(sp, "b", param)
        if op.has_body:
            sp.add_argument("--json", dest="json_body", default=None, metavar="JSON|@FILE",
                            help="request body as a JSON object or @file; explicit flags override it")
        if op.write:
            sp.add_argument("--dry-run", dest="dry_run", action="store_true",
                            help="print the request that would be sent, send nothing")
        if op.paged:
            sp.add_argument("--page-all", dest="page_all", action="store_true",
                            help="follow the cursor and print one JSON line per page")
            sp.add_argument("--page-limit", dest="page_limit", type=int, default=10, metavar="N",
                            help="maximum pages with --page-all (default 10, 0 = unlimited)")
        sp.add_argument("--out", default=None, metavar="FILE", help="write the JSON result to FILE")
        sp.set_defaults(op=op)
    return resources


def _load_json_arg(text: str) -> dict:
    if text.startswith("@"):
        try:
            with open(text[1:], "r", encoding="utf-8") as f:
                text = f.read()
        except OSError as e:
            raise UsageError("cannot read %s: %s" % (text[1:], e.strerror or e))
    try:
        value = json.loads(text)
    except ValueError as e:
        raise UsageError("--json is not valid JSON: %s" % e)
    if not isinstance(value, dict):
        raise UsageError("--json must be a JSON object")
    return value


def _query_of(op: Op, args) -> dict:
    query = {p.name: getattr(args, _dest("q", p), None) for p in op.query}
    missing = [p.flag for p in op.query if p.required and query[p.name] is None]
    if missing:
        raise UsageError("missing required: %s" % ", ".join(missing))
    return query


def _apply_defaults(body: dict, defaults: Dict[str, Any]) -> None:
    """Fill keys the body lacks; a key present with a JSON null is the caller's choice and is kept."""
    for key, value in defaults.items():
        if key not in body:
            body[key] = copy.deepcopy(value)


def _body_of(op: Op, args) -> Optional[dict]:
    if not op.has_body:
        return None
    body = {}  # type: dict
    raw = getattr(args, "json_body", None)
    json_obj = _load_json_arg(raw) if raw is not None else {}
    args.json_obj = json_obj  # build_body callbacks read it to combine with the flags
    body.update(json_obj)
    if op.build_body is not None:
        body.update(op.build_body(args))
    else:
        for p in op.body:
            value = getattr(args, _dest("b", p), None)
            if value is not None:
                body[p.name] = value
    _apply_defaults(body, op.body_defaults)
    if op.body_required and not body:
        raise UsageError("give at least one of: %s (or supply it via --json)"
                         % ", ".join(p.flag for p in op.body))
    missing = [p.flag for p in op.body if p.required and p.name not in body]
    if missing:
        raise UsageError("missing required: %s (or supply it via --json)" % ", ".join(missing))
    return body


def run(op: Op, args, client: Client) -> int:
    path = op.path
    for pname in op.path_params:
        value = str(getattr(args, "pp_" + pname))
        if value in (".", ".."):  # quote() keeps dots, and the URL would resolve to another endpoint
            raise UsageError("%s must not be '.' or '..'" % pname.upper())
        path = path.replace("{%s}" % pname, quote(value, safe=""))
    query = _query_of(op, args)
    body = _body_of(op, args)
    out = getattr(args, "out", None)
    if op.paged and getattr(args, "page_all", False):
        if body is not None:
            _apply_defaults(body, op.page_all_defaults)
            if "sort" in op.page_all_defaults and body.get("sort") is None:
                # "sort": null from --json: the API returns no cursor, paging would stop after one page
                raise UsageError("--page-all needs a sort (--json gave \"sort\": null)")
        pages = client.paginate(
            op.method, path, query=query, body=body,
            cursor_in="body" if op.has_body else "query",
            page_limit=getattr(args, "page_limit", 10),
        )
        if out:
            with atomic_writer(out) as f:  # nothing lands unless every page was fetched
                for page in pages:
                    emit_line(page, stream=f)
        else:
            for page in pages:
                emit_line(page)
        return 0
    result = client.request(
        op.method, path, query=query, body=body, write=op.write,
        dry_run=bool(getattr(args, "dry_run", False)),
    )
    emit(result, out=out)
    return 0
