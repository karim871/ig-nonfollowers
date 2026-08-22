"""Run: python test_parser.py"""
import sys
import time
from datetime import datetime, timedelta

from core import (
    add_to_ignore_list,
    compute_diff,
    days_waiting,
    diff_since_snapshot,
    merge_ignore_states,
    new_ignore_state,
    new_snapshot_state,
    normalize_ignore_state,
    normalize_snapshot_state,
    parse_export,
    remove_from_ignore_list,
    split_by_ignore_list,
    update_snapshot,
)


def make_entry(username, ts=1700000000, href=None):
    return {
        "title": "",
        "media_list_data": [],
        "string_list_data": [{
            "href": href or f"https://www.instagram.com/{username}/",
            "value": username,
            "timestamp": ts,
        }]
    }


failures = []


def check(label, got, expected):
    ok = got == expected
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {label}: {got!r}")
    if not ok:
        print(f"         expected: {expected!r}")
        failures.append(label)


print("-- parse_export --")

# 1. followers format: list at root
data = [make_entry("alice"), make_entry("bob")]
r = parse_export(data)
check("list-at-root count", len(r), 2)
check("list-at-root username", r[0]["username"], "alice")

# 2. following format: dict wrapper
data = {"relationships_following": [make_entry("charlie")]}
r = parse_export(data)
check("dict-wrapper count", len(r), 1)
check("dict-wrapper username", r[0]["username"], "charlie")

# 3. empty list
check("empty list", parse_export([]), [])

# 4. empty dict
check("empty dict", parse_export({}), [])

# 5. missing href constructs URL
entry = make_entry("dave")
entry["string_list_data"][0].pop("href")
r = parse_export([entry])
check("missing href builds url", r[0]["url"], "https://www.instagram.com/dave/")

# 6. timestamp = 0 shows dash
r = parse_export([make_entry("eve", ts=0)])
check("timestamp 0 shows dash", r[0]["date"], "—")

# 7. missing timestamp shows dash
entry = make_entry("frank")
entry["string_list_data"][0].pop("timestamp")
r = parse_export([entry])
check("missing timestamp shows dash", r[0]["date"], "—")

# 8. blank username skipped
check("blank username skipped", parse_export([make_entry("")]), [])

# 9. whitespace username skipped
check("whitespace username skipped", parse_export([make_entry("   ")]), [])

# 10. following.json shape: username in item title, no "value"
following_entry = {
    "title": "gina",
    "media_list_data": [],
    "string_list_data": [{"href": "https://www.instagram.com/_u/gina/", "timestamp": 1700000000}],
}
r = parse_export([following_entry])
check("title-based username", r[0]["username"], "gina")
check("/_u/ href normalised", r[0]["url"], "https://www.instagram.com/gina/")

# 11. multiple followers files merged
merged = parse_export([make_entry("alice")]) + parse_export([make_entry("bob")])
check("merged followers files", len(merged), 2)

# 12. date format for valid timestamp
r = parse_export([make_entry("grace", ts=1700000000)])
check("date format non-empty", len(r[0]["date"]) > 0, True)

# 13. raw timestamp preserved for downstream day-counting
r = parse_export([make_entry("henry", ts=1700000000)])
check("timestamp preserved", r[0]["timestamp"], 1700000000)


print("\n-- compute_diff --")

following_parsed = parse_export([make_entry(u) for u in ["alice", "bob", "charlie"]])
followers_parsed = parse_export([make_entry(u) for u in ["alice", "dave"]])
diff = compute_diff(followers_parsed, following_parsed)
check("not-following-back count", len(diff["not_following_back"]), 2)
check(
    "not-following-back names",
    sorted(u["username"] for u in diff["not_following_back"]),
    ["bob", "charlie"],
)
check("you-dont-follow count", len(diff["you_dont_follow"]), 1)
check("you-dont-follow names", diff["you_dont_follow"][0]["username"], "dave")
check("mutual count", diff["mutual_count"], 1)


print("\n-- days_waiting --")

now = datetime(2026, 8, 8, 12, 0, 0)
five_days_ago = int((now - timedelta(days=5)).timestamp())
check("5 days elapsed", days_waiting(five_days_ago, now=now), 5)
check("zero timestamp is unknown", days_waiting(0, now=now), None)
check("missing timestamp is unknown", days_waiting(None, now=now), None)
just_now = int(now.timestamp())
check("just followed is 0 days", days_waiting(just_now, now=now), 0)


print("\n-- ignore list --")

state = new_ignore_state()
check("new state is empty", state["usernames"], {})

state = add_to_ignore_list(state, ["brandco", "celeb1"], today="2026-08-01")
check("added two usernames", sorted(state["usernames"]), ["brandco", "celeb1"])
check("recorded date", state["usernames"]["brandco"], "2026-08-01")

# adding an existing username again doesn't overwrite its original date
state = add_to_ignore_list(state, ["brandco"], today="2026-08-08")
check("re-adding keeps original date", state["usernames"]["brandco"], "2026-08-01")

pending, ignored = split_by_ignore_list(diff["not_following_back"], state["usernames"])
check("split excludes ignored from pending", "charlie" not in [u["username"] for u in ignored], True)

state = add_to_ignore_list(state, ["charlie"], today="2026-08-08")
pending, ignored = split_by_ignore_list(diff["not_following_back"], state["usernames"])
check("split moves charlie to ignored", [u["username"] for u in ignored], ["charlie"])
check("split leaves bob pending", [u["username"] for u in pending], ["bob"])

state = remove_from_ignore_list(state, ["charlie"])
check("un-ignore removes username", "charlie" in state["usernames"], False)

# normalize_ignore_state tolerates garbage input
check("normalize handles None", normalize_ignore_state(None)["usernames"], {})
check("normalize handles junk dict", normalize_ignore_state({"foo": "bar"})["usernames"], {})
check(
    "normalize keeps valid shape",
    normalize_ignore_state({"version": 1, "usernames": {"x": "2026-01-01"}})["usernames"],
    {"x": "2026-01-01"},
)

# merge keeps the earliest date per username, unions the rest
a = add_to_ignore_list(new_ignore_state(), ["shared", "only_a"], today="2026-08-05")
b = add_to_ignore_list(new_ignore_state(), ["shared", "only_b"], today="2026-08-01")
merged = merge_ignore_states(a, b)
check("merge unions usernames", sorted(merged["usernames"]), ["only_a", "only_b", "shared"])
check("merge keeps earliest date for shared username", merged["usernames"]["shared"], "2026-08-01")


print("\n-- snapshot history --")

snap = new_snapshot_state()
check("new snapshot has no checked_at", snap["checked_at"], None)
check("no diff before any check happened", diff_since_snapshot({"alice", "bob"}, snap), None)

snap = update_snapshot({"alice", "bob"}, checked_at="2026-08-01")
check("update records followers", snap["followers"], ["alice", "bob"])
check("update records checked_at", snap["checked_at"], "2026-08-01")

d = diff_since_snapshot({"alice", "charlie"}, snap)
check("lost follower detected", d["lost_followers"], ["bob"])
check("new follower detected", d["new_followers"], ["charlie"])
check("diff carries forward the snapshot date", d["since"], "2026-08-01")

d = diff_since_snapshot({"alice", "bob"}, snap)
check("no changes reports empty lists", (d["new_followers"], d["lost_followers"]), ([], []))

# normalize_snapshot_state tolerates garbage input
check("normalize handles None", normalize_snapshot_state(None)["followers"], [])
check("normalize handles junk dict", normalize_snapshot_state({"foo": "bar"})["followers"], [])
check(
    "normalize keeps valid shape",
    normalize_snapshot_state({"version": 1, "checked_at": "2026-08-01", "followers": ["x"]}),
    {"version": 1, "checked_at": "2026-08-01", "followers": ["x"]},
)


print()
if failures:
    print(f"FAILED: {len(failures)} test(s): {failures}")
    sys.exit(1)
else:
    print("All tests passed.")
