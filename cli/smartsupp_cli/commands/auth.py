"""`auth setup` (store the token) and `auth check` (probe scopes); not Ops: local or multi-request."""
import datetime
import getpass
import os
import sys
import tempfile
from pathlib import Path
from typing import List

from ..client import Client
from ..config import config_path, load_config
from ..errors import ApiError, AuthError, CliError, UsageError, reason_of
from ..output import emit
from .statistics import build_stats_body

TOKEN_VAR = "SMARTSUPP_API_TOKEN"
DEFAULT_SCOPES = "conversations:read,contacts:read,tags:read"
UNVERIFIABLE = ("visitors:read", "bots:read")


def _today() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def _probe_conversations(client):
    client.request("POST", "/conversations/search", body={"size": 1})


def _probe_contacts(client):
    try:
        client.request("GET", "/contacts/find", query={"email": "support@smartsupp.com"})
    except ApiError as e:
        if e.status != 404:  # an unknown contact still proves the scope
            raise


def _probe_tags(client):
    client.request("GET", "/tags")


def _probe_statistics(client):
    day = _today()
    body = build_stats_body(["new_conversation"], day, day, None, [])
    client.request("POST", "/statistics", query={"timezone": "UTC"}, body=body)


def _probe_agents(client):
    client.request("GET", "/agents")


PROBES = {
    "conversations:read": _probe_conversations,
    "contacts:read": _probe_contacts,
    "tags:read": _probe_tags,
    "statistics:read": _probe_statistics,
    "agents:read": _probe_agents,
}


def _updated_lines(existing: str, token: str) -> str:
    new_line = "%s=%s" % (TOKEN_VAR, token)
    lines = existing.splitlines()
    out = []  # type: List[str]
    replaced = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("export ") or stripped.startswith("export\t"):
            stripped = stripped[len("export"):].lstrip()
        if stripped.partition("=")[0].strip() == TOKEN_VAR and "=" in stripped:
            if not replaced:
                out.append(new_line)
                replaced = True
            continue
        out.append(line)
    if not replaced:
        out.append(new_line)
    return "\n".join(out) + "\n"


def _write_atomic(path: Path, text: str) -> None:
    # a symlinked config stays a link: write the file it points to
    target = Path(os.path.realpath(str(path)))
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(str(path.parent), 0o700)  # tighten an existing directory; never delete anything
    except PermissionError:
        print("warning: could not set %s to mode 0700 (not the owner?); continuing" % path.parent,
              file=sys.stderr)
    path = target
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(tmp, 0o600)
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _setup_handler(args) -> int:
    if not sys.stdin.isatty():
        raise UsageError("auth setup needs an interactive terminal; the token is never read from arguments or pipes")
    token = getpass.getpass("Smartsupp API token: ").strip()
    if not token:
        raise UsageError("no token entered")
    path = config_path(os.environ)
    try:
        try:
            existing = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            existing = ""
        _write_atomic(path, _updated_lines(existing, token))
    except (OSError, UnicodeDecodeError) as e:
        what = e.strerror if isinstance(e, OSError) and e.strerror else type(e).__name__
        raise CliError("cannot update the config file %s: %s" % (path, what))
    emit({"ok": True, "path": str(path)})
    return 0


def _check_handler(args) -> int:
    scopes = [s.strip() for s in args.scopes.split(",") if s.strip()]
    if not scopes:
        raise UsageError("--scopes needs at least one scope; known: %s"
                         % ", ".join(list(PROBES) + list(UNVERIFIABLE)))
    unknown = [s for s in scopes if s not in PROBES and s not in UNVERIFIABLE]
    if unknown:
        raise UsageError("unknown scope(s): %s; known: %s"
                         % (", ".join(unknown), ", ".join(list(PROBES) + list(UNVERIFIABLE))))
    client = Client(load_config())
    failed = []  # type: List[str]
    reasons = {}  # type: dict
    unverifiable = []  # type: List[str]
    auth_failed = False
    for scope in scopes:
        if scope in UNVERIFIABLE:
            unverifiable.append(scope)
            continue
        try:
            PROBES[scope](client)
        except AuthError as e:
            failed.append(scope)
            reasons[scope] = reason_of(e)
            auth_failed = True
        except CliError as e:
            failed.append(scope)
            reasons[scope] = reason_of(e)
    verified = len(scopes) - len(unverifiable)
    result = {"ok": not failed and verified > 0}  # type: dict
    if failed:
        result["failed"] = failed
        result["reasons"] = reasons
    if unverifiable:
        result["unverifiable"] = unverifiable
    emit(result)
    if auth_failed:
        return 2
    return 0 if result["ok"] else 1


def register(subparsers) -> None:
    auth = subparsers.add_parser("auth", help="store the API token and check its scopes")
    sub = auth.add_subparsers(dest="auth_command", parser_class=type(auth))
    setup = sub.add_parser("setup", help="prompt for the token and save it to the config file")
    setup.set_defaults(handler=_setup_handler)
    check = sub.add_parser("check", help="probe the token's scopes (exit 0 ok, 2 auth failure, 1 other)")
    check.add_argument("--scopes", default=DEFAULT_SCOPES,
                       help="comma-separated scopes (default %s)" % DEFAULT_SCOPES)
    check.set_defaults(handler=_check_handler)
