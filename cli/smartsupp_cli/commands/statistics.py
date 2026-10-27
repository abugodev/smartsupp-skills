from typing import List, Optional

from ..errors import UsageError
from ..ops import Op, Param
from ..search import split_clause, day_range, parse_range, parse_value

METRICS = ("response_time", "first_response_time", "time_to_close", "time_to_close_sum",
           "new_conversation", "closed_conversation", "conversation_ratings")
INTERVALS = ("day", "week", "month", "year", "day_of_week", "hour_of_day")


def build_stats_body(metrics: List[str], date_from: Optional[str], date_to: Optional[str],
                     group_by: Optional[str], filters: List[str]) -> dict:
    """Request body keyed by result name (metric name, `_2`, `_3` on repeats)."""
    query = []  # type: List[dict]
    for text in filters:
        field, value = split_clause(text, "--filter")
        query.append({"field": field, "value": parse_value(value)})
    if group_by is None:
        aggs = None
    elif group_by in INTERVALS:
        aggs = [{"type": "date", "interval": group_by}]
    else:
        aggs = [{"type": "terms", "field": group_by}]
    shared = None
    if (date_from is None) != (date_to is None):
        raise UsageError("--from and --to go together: give both or neither")
    if date_from is not None:
        if all(":" in m for m in metrics):  # they would apply to no metric: never drop them silently
            raise UsageError("--from/--to apply to no metric: every --metric has its own :FROM..TO")
        shared = day_range(date_from, date_to)
    body = {}  # type: dict
    seen = {}  # type: dict
    for text in metrics:
        name, sep, rng = text.partition(":")
        if name not in METRICS:
            raise UsageError("unknown metric %r; one of: %s" % (name, ", ".join(METRICS)))
        window = parse_range(rng, "--metric") if sep else shared
        if window is None:
            raise UsageError("--from and --to are required unless every --metric has :FROM..TO")
        seen[name] = seen.get(name, 0) + 1
        key = name if seen[name] == 1 else "%s_%d" % (name, seen[name])
        item = {"name": name, "range": {"from": window[0], "to": window[1]}}  # type: dict
        if query:
            item["query"] = [dict(c) for c in query]
        if aggs:
            item["aggs"] = [dict(a) for a in aggs]
        body[key] = item
    return body


def _query_body(args) -> dict:
    if args.q_timezone is not None and not args.q_timezone.strip():
        raise UsageError("--timezone must not be empty")
    if not args.b_metric:
        if args.b_from is not None or args.b_to is not None:
            raise UsageError("--from/--to apply to --metric; with a --json body set the ranges in it")
        if getattr(args, "json_body", None) is None:
            raise UsageError("missing required: --metric (or supply the body via --json)")
        return {}
    return build_stats_body(args.b_metric, args.b_from, args.b_to, args.b_group_by,
                            args.b_filter or [])


OPS = [
    Op("statistics", "query", "POST", "/statistics", False, "statistics:read",
       "Query statistics (UTC day windows)",
       query=[Param("timezone", "--timezone", default="UTC",
                    help="timezone for the request, e.g. Europe/Prague (default UTC)")],
       body=[
           Param("metric", "--metric", repeat=True,
                 help="NAME or NAME:FROM..TO, repeatable; one of: " + ", ".join(METRICS)),
           Param("from", "--from", help="YYYY-MM-DD start day (UTC), shared by metrics without own range"),
           Param("to", "--to", help="YYYY-MM-DD end day (UTC), inclusive"),
           Param("group_by", "--group-by",
                 help="interval (%s) or a field to group by (terms)" % ", ".join(INTERVALS)),
           Param("filter", "--filter", repeat=True, help="FIELD=VALUE on every metric, repeatable"),
       ],
       build_body=_query_body),
]
