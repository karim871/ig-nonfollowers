"""Run: python test_parser.py"""
import sys
from datetime import datetime

def parse_export(data):
    items = data if isinstance(data, list) else next(iter(data.values()), [])
    result = []
    for item in items:
        for entry in item.get("string_list_data", []):
            username = entry.get("value", "").strip()
            if not username:
                continue
            ts = entry.get("timestamp", 0)
            result.append({
                "username": username,
                "url": entry.get("href") or f"https://www.instagram.com/{username}/",
                "date": datetime.fromtimestamp(ts).strftime("%b %d, %Y") if ts else "-",
            })
    return result

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
check("timestamp 0 shows dash", r[0]["date"], "-")

# 7. missing timestamp shows dash
entry = make_entry("frank")
entry["string_list_data"][0].pop("timestamp")
r = parse_export([entry])
check("missing timestamp shows dash", r[0]["date"], "-")

# 8. blank username skipped
check("blank username skipped", parse_export([make_entry("")]), [])

# 9. whitespace username skipped
check("whitespace username skipped", parse_export([make_entry("   ")]), [])

# 10. non-follower diff logic
following_parsed = parse_export([make_entry(u) for u in ["alice", "bob", "charlie"]])
followers_parsed = parse_export([make_entry(u) for u in ["alice", "dave"]])
followers_set = {u["username"] for u in followers_parsed}
not_back = [u for u in following_parsed if u["username"] not in followers_set]
check("not-following-back count", len(not_back), 2)
check("not-following-back names", sorted(u["username"] for u in not_back), ["bob", "charlie"])

# 11. multiple followers files merged
merged = parse_export([make_entry("alice")]) + parse_export([make_entry("bob")])
check("merged followers files", len(merged), 2)

# 12. date format for valid timestamp
r = parse_export([make_entry("grace", ts=1700000000)])
check("date format non-empty", len(r[0]["date"]) > 0, True)

print()
if failures:
    print(f"FAILED: {len(failures)} test(s): {failures}")
    sys.exit(1)
else:
    print("All tests passed.")
