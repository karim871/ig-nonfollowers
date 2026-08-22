"""Pure data logic for ig-nonfollowers — no Streamlit imports, so it's importable
from tests without booting an app context."""
from datetime import datetime, timezone

IGNORE_STATE_VERSION = 1


# ── parsing ──────────────────────────────────────────────────────────────────

def parse_export(data: dict | list) -> list[dict]:
    """Accept both Instagram export shapes (list-at-root or dict-wrapped)."""
    items = data if isinstance(data, list) else next(iter(data.values()), [])
    result = []
    for item in items:
        for entry in item.get("string_list_data", []):
            # followers_*.json puts username in entry["value"];
            # following.json omits "value" and puts it in the parent item["title"]
            username = (entry.get("value") or item.get("title") or "").strip()
            if not username:
                continue
            ts = entry.get("timestamp", 0)
            href = entry.get("href", "")
            # Instagram's following export uses /_u/ redirect URLs — normalise to clean profile URL
            if "/_u/" in href:
                href = f"https://www.instagram.com/{username}/"
            result.append({
                "username": username,
                "url": href or f"https://www.instagram.com/{username}/",
                "timestamp": ts,
                "date": datetime.fromtimestamp(ts).strftime("%b %d, %Y") if ts else "—",
            })
    return result


# ── diffing ──────────────────────────────────────────────────────────────────

def compute_diff(followers: list[dict], following: list[dict]) -> dict:
    """Compare two parsed lists and return the sets that matter for the growth loop."""
    followers_set = {u["username"] for u in followers}
    following_set = {u["username"] for u in following}

    not_following_back = [u for u in following if u["username"] not in followers_set]
    you_dont_follow = [u for u in followers if u["username"] not in following_set]
    mutual_count = len(followers_set & following_set)

    return {
        "followers_set": followers_set,
        "following_set": following_set,
        "not_following_back": not_following_back,
        "you_dont_follow": you_dont_follow,
        "mutual_count": mutual_count,
    }


# ── wait-time (the "did they follow back yet?" clock) ───────────────────────

def days_waiting(timestamp: int, now: datetime | None = None) -> int | None:
    """Days elapsed since `timestamp` (the moment you followed them). None if unknown."""
    if not timestamp:
        return None
    now = now or datetime.now()
    followed_at = datetime.fromtimestamp(timestamp)
    return max((now - followed_at).days, 0)


def split_by_ignore_list(rows: list[dict], ignored: dict) -> tuple[list[dict], list[dict]]:
    """Split rows into (pending, ignored) based on username membership in `ignored`."""
    pending = [r for r in rows if r["username"] not in ignored]
    ignored_rows = [r for r in rows if r["username"] in ignored]
    return pending, ignored_rows


# ── ignore list persistence helpers ──────────────────────────────────────────

def new_ignore_state() -> dict:
    return {"version": IGNORE_STATE_VERSION, "usernames": {}}


def normalize_ignore_state(raw: dict | None) -> dict:
    """Coerce whatever we loaded (old shape, partial, junk) into the canonical shape."""
    if not isinstance(raw, dict):
        return new_ignore_state()
    usernames = raw.get("usernames")
    if not isinstance(usernames, dict):
        return new_ignore_state()
    clean = {
        str(k): str(v) for k, v in usernames.items()
        if isinstance(k, str) and k.strip()
    }
    return {"version": IGNORE_STATE_VERSION, "usernames": clean}


def add_to_ignore_list(state: dict, usernames: list[str], today: str | None = None) -> dict:
    today = today or datetime.now().strftime("%Y-%m-%d")
    state = normalize_ignore_state(state)
    for u in usernames:
        state["usernames"].setdefault(u, today)
    return state


def remove_from_ignore_list(state: dict, usernames: list[str]) -> dict:
    state = normalize_ignore_state(state)
    for u in usernames:
        state["usernames"].pop(u, None)
    return state


def merge_ignore_states(a: dict, b: dict) -> dict:
    """Union two ignore states, keeping the earliest recorded date for each username."""
    a = normalize_ignore_state(a)
    b = normalize_ignore_state(b)
    merged = dict(a["usernames"])
    for username, added in b["usernames"].items():
        if username not in merged or added < merged[username]:
            merged[username] = added
    return {"version": IGNORE_STATE_VERSION, "usernames": merged}


# ── snapshot history (the "what changed since I last checked?" clock) ───────

SNAPSHOT_STATE_VERSION = 1


def new_snapshot_state() -> dict:
    return {"version": SNAPSHOT_STATE_VERSION, "checked_at": None, "followers": []}


def normalize_snapshot_state(raw: dict | None) -> dict:
    """Coerce whatever we loaded (old shape, partial, junk) into the canonical shape."""
    if not isinstance(raw, dict):
        return new_snapshot_state()
    followers = raw.get("followers")
    checked_at = raw.get("checked_at")
    if not isinstance(followers, list):
        return new_snapshot_state()
    return {
        "version": SNAPSHOT_STATE_VERSION,
        "checked_at": checked_at if isinstance(checked_at, str) and checked_at else None,
        "followers": sorted({str(u) for u in followers if isinstance(u, str) and u.strip()}),
    }


def diff_since_snapshot(followers_set: set, snapshot: dict) -> dict | None:
    """Compare current followers to the last recorded snapshot. None if there's nothing to compare against yet."""
    snapshot = normalize_snapshot_state(snapshot)
    if not snapshot["checked_at"]:
        return None
    prev_followers = set(snapshot["followers"])
    return {
        "since": snapshot["checked_at"],
        "new_followers": sorted(followers_set - prev_followers),
        "lost_followers": sorted(prev_followers - followers_set),
    }


def update_snapshot(followers_set: set, checked_at: str | None = None) -> dict:
    checked_at = checked_at or datetime.now().strftime("%b %d, %Y")
    return {
        "version": SNAPSHOT_STATE_VERSION,
        "checked_at": checked_at,
        "followers": sorted(followers_set),
    }
