"""`conversations +fetch`: write the smartsupp-conversations workspace (raw/, contacts/, manifest.json).

Produces the same files as the skill's MCP fetch step. Nothing it prints or records outside
raw/ and contacts/ may contain contact fields or message text: errors are reduced to status codes.
"""
import json
import os
import re
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import quote

from .. import __version__
from ..client import Client
from ..errors import ApiError, reason_of
from ..search import day_range

DEFAULT_EXCLUDE = ("eval-exclude", "exclude_from_cx", "spam", "test")
TAG_FIELD = "tags"  # search field for conversation tags; assumed, confirm against the live API
STATUSES = ("closed", "open", "all")
PAGE_SIZE = 100
TMP_PREFIX = ".fetch-tmp-"

CONV_KEYS = ("id", "created_at", "finished_at", "status", "channel", "domain", "contact_id",
             "rating_value", "rating_text", "tags")
MSG_KEYS = ("created_at", "type", "sub_type", "agent_id", "trigger_id", "trigger_name", "page_url")
CONTENT_KEYS = ("type", "text", "data")
CONTACT_KEYS = ("id", "name", "email", "phone")

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def _items(page: Any) -> List[dict]:
    if isinstance(page, list):
        return page
    if isinstance(page, dict):
        return page.get("items") or page.get("data") or []
    return []


def _write_json(path: Path, data: Any) -> None:
    """Temp file in the target dir + os.replace: the target is either old or complete, never partial."""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=TMP_PREFIX, suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
            f.write("\n")
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _remove_stray_temp_files(*dirs: Path) -> None:
    for d in dirs:
        for p in d.glob(TMP_PREFIX + "*"):
            try:
                p.unlink()
            except OSError:
                pass


def _move_manifest_aside(ws: Path) -> None:
    """Keep the previous manifest as manifest.previous.json; an older one there moves to .1, .2, ..."""
    current = ws / "manifest.json"
    if not current.exists():
        return
    previous = ws / "manifest.previous.json"
    if previous.exists():
        n = 1
        while (ws / ("manifest.previous.%d.json" % n)).exists():
            n += 1
        os.replace(str(previous), str(ws / ("manifest.previous.%d.json" % n)))
    os.replace(str(current), str(previous))


def _compact_message(m: dict) -> dict:
    out = {k: m.get(k) for k in MSG_KEYS}
    content = m.get("content") or {}
    out["content"] = {k: content.get(k) for k in CONTENT_KEYS}
    out["attachments"] = m.get("attachments")
    return out


def _compact_conversation(conv: dict, messages: List[dict]) -> dict:
    out = {k: conv.get(k) for k in CONV_KEYS}
    out["messages"] = {"items": [_compact_message(m) for m in messages]}
    return out


def _all_messages(client: Client, conv: dict) -> List[dict]:
    """Messages embedded in the conversation (at most 200), then the rest via the messages API."""
    collection = conv.get("messages") or {}
    merged = []  # type: List[dict]
    seen = set()

    def add(items):
        for m in items:
            mid = m.get("id") if isinstance(m, dict) else None
            if mid is not None:
                if mid in seen:
                    continue
                seen.add(mid)
            merged.append(m)

    add(collection.get("items") or [])
    after = collection.get("after")
    if after not in (None, "", []):
        path = "/conversations/%s/messages" % quote(conv["id"], safe="")
        for page in client.paginate("GET", path, query={"size": PAGE_SIZE, "after": after}, page_limit=0):
            add(_items(page))
    return merged


def _current(path: Path, finished_at: Any) -> Optional[dict]:
    """The raw file already on disk when it is complete and has the same finished_at, else None."""
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if isinstance(existing, dict) and existing.get("finished_at") == finished_at:
        return existing
    return None


def _tag_ids(conv: Any) -> set:
    """Tag ids of a conversation; tags have the shape {"data": [{"id": ...}]}."""
    tags = conv.get("tags") if isinstance(conv, dict) else None
    data = tags.get("data") if isinstance(tags, dict) else tags
    if not isinstance(data, list):
        return set()
    return {t.get("id") for t in data if isinstance(t, dict) and t.get("id") is not None}


def _excluded_tags(client: Client, names: Sequence[str]) -> Tuple[List[dict], List[str]]:
    """Account tags matching `names` (case-insensitive): those with an id, and names of those without."""
    wanted = {n.strip().lower() for n in names if n.strip()}
    if not wanted:
        return [], []
    matching = [t for t in _items(client.request("GET", "/tags"))
                if isinstance(t, dict) and str(t.get("name", "")).lower() in wanted]
    with_id = {str(t.get("name", "")).lower() for t in matching if t.get("id") is not None}
    without_id = []  # type: List[str]
    for t in matching:  # a name also listed with an id is excluded through that id: no warning
        name = str(t.get("name", ""))
        if t.get("id") is None and name.lower() not in with_id and name not in without_id:
            without_id.append(name)
    return [t for t in matching if t.get("id") is not None], without_id


def _search_body(date_from: str, date_to: str, status: str, timezone: str, tags: List[dict]) -> dict:
    """One search: closed chats by finished_at, open chats by created_at (open ones have no finished_at)."""
    field = "created_at" if status == "open" else "finished_at"
    query = [{"field": "status", "value": status},
             {"field": field, "value": day_range(date_from, date_to)}]  # type: List[dict]
    for tag in tags:
        query.append({"field": TAG_FIELD, "value": tag["id"], "op": "must_not"})
    return {"size": PAGE_SIZE, "timezone": timezone, "query": query, "sort": [{field: "asc"}]}


def _search(client: Client, bodies: Sequence[dict]) -> List[dict]:
    """Run each search and merge the results by conversation id, first occurrence wins."""
    found = []  # type: List[dict]
    seen = set()
    for body in bodies:
        for page in client.paginate("POST", "/conversations/search", body=body, cursor_in="body", page_limit=0):
            for item in _items(page):
                if isinstance(item, dict) and item.get("id") not in seen:
                    seen.add(item.get("id"))
                    found.append(item)
    return found


def _quiet(what: str, call):
    """Run a top-level request; on failure keep only the status (response bodies may hold personal data)."""
    try:
        return call()
    except ApiError as e:
        raise ApiError("%s failed (%s)" % (what, "network error" if e.status is None else "HTTP %d" % e.status),
                       status=e.status)


def run_fetch(
    client: Client,
    ws: Path,
    date_from: str,
    date_to: str,
    status: str = "closed",
    exclude_tags: Sequence[str] = DEFAULT_EXCLUDE,
    timezone: str = "UTC",
    workers: int = 4,
) -> dict:
    """Fetch the window into `ws` and return the manifest (also written to ws/manifest.json)."""
    if status not in STATUSES:
        raise ValueError("status must be one of %s" % ", ".join(STATUSES))
    day_range(date_from, date_to)  # validate dates before any request
    ws = Path(ws)
    raw_dir, contacts_dir = ws / "raw", ws / "contacts"
    raw_dir.mkdir(parents=True, exist_ok=True)
    contacts_dir.mkdir(parents=True, exist_ok=True)
    _remove_stray_temp_files(ws, raw_dir, contacts_dir)
    # an aborted run must not look like a finished one: the manifest says complete=false until the end
    _move_manifest_aside(ws)
    _write_json(ws / "manifest.json", {"window": {"from": date_from, "to": date_to, "timezone": timezone},
                                       "route": "cli", "cli_version": __version__, "complete": False})

    tags, tags_without_id = _quiet("tags list", lambda: _excluded_tags(client, exclude_tags))
    for name in tags_without_id:  # a tag name, never conversation or contact data
        sys.stderr.write("warning: excluded tag %r has no id; conversations carrying it are not excluded\n" % name)
    statuses = ("closed", "open") if status == "all" else (status,)
    bodies = [_search_body(date_from, date_to, s, timezone, tags) for s in statuses]
    found = _quiet("conversations search", lambda: _search(client, bodies))
    excluded_ids = {t.get("id") for t in tags if t.get("id") is not None}

    skipped = []  # type: List[dict]
    fetched = 0
    resumed = 0
    excluded = 0
    RESUMED = "resumed"  # fetch_one result: raw/<id>.json from an earlier run is current
    EXCLUDED = "excluded"  # fetch_one result: carries an excluded tag, nothing kept

    def drop(target: Path) -> str:
        # a file from an earlier run must not stay in the analysis, but it is never deleted:
        # move it to <ws>/excluded/, next to (not over) any copy already there
        if target.exists():
            dest_dir = ws / "excluded"
            dest_dir.mkdir(exist_ok=True)
            dest = dest_dir / target.name
            n = 1
            while dest.exists():
                dest = dest_dir / ("%s.%d.json" % (target.stem, n))
                n += 1
            os.replace(str(target), str(dest))
        return EXCLUDED

    def fetch_one(item: dict) -> Any:
        """Returns a skipped entry, EXCLUDED, RESUMED (raw/<id>.json is current) or None (newly fetched)."""
        cid = item.get("id")
        if not isinstance(cid, str) or not _SAFE_ID.match(cid):
            return {"id": cid, "reason": "invalid id"}
        target = raw_dir / ("%s.json" % cid)
        # client-side exclusion as well as the must_not clause, in case the server ignores it
        if _tag_ids(item) & excluded_ids:
            return drop(target)
        if item.get("finished_at") is not None:
            existing = _current(target, item.get("finished_at"))
            if existing is not None:
                return drop(target) if _tag_ids(existing) & excluded_ids else RESUMED
        try:
            conv = client.request("GET", "/conversations/%s" % cid, query={"messages": True})
            if _tag_ids(conv) & excluded_ids:
                return drop(target)
            messages = _all_messages(client, conv)
        except ApiError as e:  # AuthError is not an ApiError: it propagates and aborts the run
            return {"id": cid, "reason": reason_of(e)}
        _write_json(target, _compact_conversation(conv, messages))
        return None

    def fetch_contact(ct: Any) -> Optional[dict]:
        if not isinstance(ct, str) or not _SAFE_ID.match(ct):
            return {"id": ct, "reason": "invalid id", "kind": "contact"}
        target = contacts_dir / ("%s.json" % ct)
        if target.exists():
            return None
        try:
            contact = client.request("GET", "/contacts/%s" % ct)
        except ApiError as e:
            return {"id": ct, "reason": reason_of(e), "kind": "contact"}
        record = {k: (contact.get(k) if isinstance(contact, dict) else None) for k in CONTACT_KEYS}
        record["id"] = ct
        _write_json(target, record)
        return None

    pool = ThreadPoolExecutor(max_workers=max(1, workers))
    try:
        results = list(pool.map(fetch_one, found))
        contact_ids = []  # type: List[str]
        for item, res in zip(found, results):
            ct = item.get("contact_id")
            if res != EXCLUDED and ct is not None and ct not in contact_ids:
                contact_ids.append(ct)
        contact_results = list(pool.map(fetch_contact, contact_ids))
    finally:
        pool.shutdown(wait=True, cancel_futures=True)

    for res in results:
        if res is None:
            fetched += 1
        elif res == EXCLUDED:
            excluded += 1
        elif res == RESUMED:
            resumed += 1
        else:
            skipped.append(res)
    contacts = 0
    for res in contact_results:
        if res is None:
            contacts += 1
        else:
            skipped.append(res)

    manifest = {
        "window": {"from": date_from, "to": date_to, "timezone": timezone},
        "route": "cli",
        "cli_version": __version__,
        "complete": True,
        "counts": {"found": len(found), "fetched": fetched, "resumed": resumed, "skipped": len(skipped), "contacts": contacts,
                   "excluded": excluded},
        "skipped": skipped,
        "excluded_tags": [t.get("name") for t in tags],
        "excluded_tags_without_id": tags_without_id,
    }  # type: Dict[str, Any]
    _write_json(ws / "manifest.json", manifest)
    return manifest
