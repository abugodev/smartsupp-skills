"""Builders for the conversations search request body."""
import json
from datetime import datetime
from typing import Any, List, Optional

from .errors import UsageError

MAX_CLAUSES = 15
MAX_SORTS = 3


def parse_value(text: str) -> Any:
    """JSON if it parses (1 -> int, ["a","b"] -> list), else the plain string."""
    try:
        return json.loads(text)
    except ValueError:
        return text


def split_clause(text: str, flag: str):
    field, sep, value = text.partition("=")
    if not sep or not field:
        raise UsageError("%s expects FIELD=VALUE, got %r" % (flag, text))
    return field, value


def _check_date(text: str) -> str:
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        raise UsageError("not a YYYY-MM-DD date: %r" % text)
    return text


def day_range(date_from: str, date_to: str) -> List[str]:
    """UTC day window: start of `date_from` through end of `date_to`."""
    return ["%sT00:00:00.000" % _check_date(date_from), "%sT23:59:59.999" % _check_date(date_to)]


def parse_range(text: str, flag: str) -> List[str]:
    """Parse FROM..TO (YYYY-MM-DD each) into a day_range."""
    date_from, sep, date_to = text.partition("..")
    if not sep or not date_from or not date_to:
        raise UsageError("%s expects FROM..TO (YYYY-MM-DD..YYYY-MM-DD), got %r" % (flag, text))
    return day_range(date_from, date_to)


def build_search_body(
    where: List[str],
    not_: List[str],
    any_: List[str],
    sort: List[str],
    size: Optional[int],
    timezone: Optional[str],
    after: Optional[str],
    extra_clauses: Optional[List[dict]] = None,
    base_clauses: Optional[List[dict]] = None,
) -> dict:
    """`base_clauses` (from --json) come first; the flag clauses are appended to them."""
    query = list(base_clauses or [])  # type: List[dict]
    for text in where:
        field, value = split_clause(text, "--where")
        query.append({"field": field, "value": parse_value(value)})
    for text in not_:
        field, value = split_clause(text, "--not")
        query.append({"field": field, "value": parse_value(value), "op": "must_not"})
    for text in any_:
        field, value = split_clause(text, "--any")
        query.append({"field": field, "value": [parse_value(v) for v in value.split(",")],
                      "op": "or"})
    query.extend(extra_clauses or [])
    if len(query) > MAX_CLAUSES:
        raise UsageError("a search takes at most %d clauses, got %d" % (MAX_CLAUSES, len(query)))
    sorts = []  # type: List[dict]
    for text in sort:
        field, _, direction = text.partition(":")
        if not field or direction not in ("asc", "desc"):
            raise UsageError("--sort expects FIELD:asc|desc, got %r" % text)
        sorts.append({field: direction})
    if len(sorts) > MAX_SORTS:
        raise UsageError("a search takes at most %d sort keys, got %d" % (MAX_SORTS, len(sorts)))
    body = {}  # type: dict
    if timezone is not None:
        if not timezone.strip():
            raise UsageError("--timezone must not be empty")
        body["timezone"] = timezone
    if query:
        body["query"] = query
    if sorts:
        body["sort"] = sorts
    if size is not None:
        body["size"] = size
    if after is not None:
        try:
            cursor = json.loads(after)
        except ValueError:
            raise UsageError("--after must be a JSON array, got %r" % after)
        if not isinstance(cursor, list):
            raise UsageError("--after must be a JSON array, got %r" % after)
        body["after"] = cursor
    return body
