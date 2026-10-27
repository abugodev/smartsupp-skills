import argparse
import os
import sys
from typing import Optional

from . import ops as ops_mod
from .client import Client
from .commands import ALL_OPS, auth, conversations
from .config import load_config
from .errors import CliError, UsageError
from .output import emit, emit_text


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError(message)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="smartsupp", description="Smartsupp REST API client")
    parser.set_defaults(handler=None)
    # Later tasks register commands on this object via parser.smartsupp_subparsers.
    parser.smartsupp_subparsers = parser.add_subparsers(dest="command", parser_class=_Parser)
    _register_schema(parser.smartsupp_subparsers)
    resources = ops_mod.register(parser.smartsupp_subparsers, ALL_OPS)
    conversations.register_helpers(resources["conversations"])
    auth.register(parser.smartsupp_subparsers)
    return parser


def _param_info(param) -> dict:
    info = {"name": param.name, "flag": param.flag, "type": param.type, "required": param.required}
    if param.help:
        info["help"] = param.help
    if param.choices:
        info["choices"] = param.choices
    if param.repeat:
        info["repeat"] = True
    return info


def op_schema(op) -> dict:
    return {
        "endpoint": "%s %s" % (op.method, op.path),
        "class": "write" if op.write else "read",
        "scope": ", ".join(op.scopes),
        "scopes": op.scopes,
        "path_params": list(op.path_params),
        "query": [_param_info(p) for p in op.query],
        "body": [_param_info(p) for p in op.body],
    }


def _schema_handler(args) -> int:
    if not args.resource:
        for op in ALL_OPS:
            emit_text("%s %s" % (op.resource, op.name))
        return 0
    if not args.method:
        raise UsageError("usage: smartsupp schema <resource> <method>")
    for op in ALL_OPS:
        if op.resource == args.resource and op.name == args.method:
            emit(op_schema(op))
            return 0
    raise UsageError("unknown command: %s %s (run 'smartsupp schema' to list them)"
                     % (args.resource, args.method))


def _register_schema(subparsers) -> None:
    sp = subparsers.add_parser("schema", help="describe a command's endpoint, scope and fields (offline)")
    sp.add_argument("resource", nargs="?")
    sp.add_argument("method", nargs="?")
    sp.set_defaults(handler=_schema_handler)


def _silence_stdout() -> None:
    """Point stdout at /dev/null so the flush at exit cannot raise BrokenPipeError again."""
    try:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
    except (OSError, ValueError, AttributeError):
        pass


def main(argv: Optional[list] = None) -> int:
    try:
        parser = build_parser()
        args = parser.parse_args(argv)
        handler = getattr(args, "handler", None)
        op = getattr(args, "op", None)
        if op is not None:  # build the client lazily: --help and schema need no token
            return ops_mod.run(op, args, Client(load_config()))
        if handler is None:  # no subcommand: usage error, help on stderr
            parser.print_help(sys.stderr)
            return UsageError.exit_code
        return handler(args) or 0
    except SystemExit as e:  # --help / --version exit through argparse
        return e.code if isinstance(e.code, int) else 0
    except CliError as e:
        print("error: %s" % e, file=sys.stderr)
        return e.exit_code
    except BrokenPipeError:  # the reader (e.g. `| head`) went away: not an error
        _silence_stdout()
        return 0
    except OSError as e:  # disk, permission and path trouble: a message, not a traceback
        print("error: %s" % (e.strerror or type(e).__name__), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
