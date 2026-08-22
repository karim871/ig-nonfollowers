import json

import pandas as pd
import streamlit as st

import core

try:
    from streamlit_javascript import st_javascript
    HAS_BROWSER_STORAGE = True
except ImportError:
    HAS_BROWSER_STORAGE = False

st.set_page_config(
    page_title="IG Non-Followers",
    page_icon="📊",
    layout="centered",
)

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; max-width: 820px; }
    [data-testid="metric-container"] {
        background: #f7f8fa;
        border-radius: 10px;
        padding: 0.8rem 1rem;
    }
    [data-testid="stFileUploaderDropzone"] { min-height: 80px; }
</style>
""", unsafe_allow_html=True)

LS_KEY = "ig_nonfollowers_ignored_v1"
LS_KEY_SNAPSHOT = "ig_nonfollowers_snapshot_v1"


# ── browser-side persistence (best-effort; backup file is the reliable path) ──

def _load_ignore_state_from_browser() -> None:
    """Poll localStorage every rerun and adopt the value once the JS bridge resolves it."""
    if not HAS_BROWSER_STORAGE:
        return
    raw = st_javascript(f"window.localStorage.getItem('{LS_KEY}')", key="ls_get")
    if raw in (0, None, "", "null"):
        return
    if raw == st.session_state.get("_ls_raw_cache"):
        return
    st.session_state._ls_raw_cache = raw
    try:
        st.session_state.ignore_state = core.normalize_ignore_state(json.loads(raw))
    except (TypeError, json.JSONDecodeError):
        pass


def _save_ignore_state_to_browser(state: dict) -> None:
    if not HAS_BROWSER_STORAGE:
        return
    payload = json.dumps(json.dumps(state))
    st_javascript(f"window.localStorage.setItem('{LS_KEY}', {payload})", key="ls_set")


def _load_snapshot_state_from_browser() -> None:
    if not HAS_BROWSER_STORAGE:
        return
    raw = st_javascript(f"window.localStorage.getItem('{LS_KEY_SNAPSHOT}')", key="snap_get")
    if raw in (0, None, "", "null"):
        return
    if raw == st.session_state.get("_snap_raw_cache"):
        return
    st.session_state._snap_raw_cache = raw
    try:
        st.session_state.snapshot_state = core.normalize_snapshot_state(json.loads(raw))
    except (TypeError, json.JSONDecodeError):
        pass


def _save_snapshot_state_to_browser(state: dict) -> None:
    if not HAS_BROWSER_STORAGE:
        return
    payload = json.dumps(json.dumps(state))
    st_javascript(f"window.localStorage.setItem('{LS_KEY_SNAPSHOT}', {payload})", key="snap_set")


if "ignore_state" not in st.session_state:
    st.session_state.ignore_state = core.new_ignore_state()
_load_ignore_state_from_browser()

# Saving via st_javascript mounts a component that needs a full script run to
# actually reach the browser and round-trip back. Calling st.rerun() right
# after mounting it tears the component down before that happens, so the
# write silently never lands in localStorage. Instead we flag "needs a save"
# and perform the save on the *next* run — the one after st.rerun() — where
# nothing interrupts it before the browser gets to execute the JS.
if st.session_state.pop("_ignore_dirty", False):
    _save_ignore_state_to_browser(st.session_state.ignore_state)

if "snapshot_state" not in st.session_state:
    st.session_state.snapshot_state = core.new_snapshot_state()
_load_snapshot_state_from_browser()


def _reset_grid_selection() -> None:
    # Grid widgets are index-keyed, so a selection would otherwise survive into
    # the next rerun and silently latch onto whatever row now occupies that
    # index once the row list is reshuffled by this action. Bumping the nonce
    # gives every st.dataframe a fresh widget key, forcing a full remount
    # instead of reusing the grid instance (which also clears its own
    # internal highlight/focus state, not just Streamlit's selection value).
    st.session_state.grid_nonce = st.session_state.get("grid_nonce", 0) + 1


def mark_as_ignored(usernames: list[str]) -> None:
    st.session_state.ignore_state = core.add_to_ignore_list(st.session_state.ignore_state, usernames)
    st.session_state._ignore_dirty = True
    _reset_grid_selection()
    st.rerun()


def unignore(usernames: list[str]) -> None:
    st.session_state.ignore_state = core.remove_from_ignore_list(st.session_state.ignore_state, usernames)
    st.session_state._ignore_dirty = True
    _reset_grid_selection()
    st.rerun()


# ── table component ───────────────────────────────────────────────────────────

def render_table(rows, tab, key, date_label, grace_days=None, action_label=None, action_fn=None,
                  empty_message="Nothing here — you're all good!"):
    with tab:
        if not rows:
            st.success(empty_message)
            return

        df = pd.DataFrame(rows)
        if grace_days is not None:
            df["days"] = df["timestamp"].apply(core.days_waiting)
            df["_sort"] = df["days"].apply(lambda d: d if d is not None else -1)
            df["status"] = df["days"].apply(
                lambda d: "❔ unknown" if d is None
                else ("🔴 unfollow now" if d >= grace_days else f"🟡 waiting ({d}d)")
            )
            df = df.sort_values("_sort", ascending=False, ignore_index=True)
        else:
            df = df.sort_values("username", ignore_index=True)

        total = len(df)
        query = st.text_input(
            "Search",
            placeholder=f"Search {total} accounts...",
            key=f"q_{key}",
            label_visibility="collapsed",
        )
        if query:
            df = df[df["username"].str.contains(query, case=False, na=False)].reset_index(drop=True)
            st.caption(f"Showing {len(df)} of {total}")

        display_cols = ["url", "date"]
        column_config = {
            "url": st.column_config.LinkColumn(
                "Username",
                display_text=r"https://www\.instagram\.com/([^/]+)",
                width="medium",
            ),
            "date": st.column_config.TextColumn(date_label, width="small"),
        }
        if grace_days is not None:
            display_cols.append("status")
            column_config["status"] = st.column_config.TextColumn("Status", width="medium")

        if action_fn is not None:
            grid_nonce = st.session_state.get("grid_nonce", 0)
            event = st.dataframe(
                df[display_cols],
                width="stretch",
                hide_index=True,
                column_config=column_config,
                on_select="rerun",
                selection_mode="multi-row",
                key=f"tbl_{key}_{grid_nonce}",
            )
            selected_idx = event.selection.rows if event and event.selection else []
            if selected_idx:
                selected_usernames = df.iloc[selected_idx]["username"].tolist()
                if st.button(f"{action_label} ({len(selected_idx)})", key=f"act_{key}", type="primary"):
                    action_fn(selected_usernames)
        else:
            st.dataframe(
                df[display_cols],
                width="stretch",
                hide_index=True,
                column_config=column_config,
            )

        col_csv, col_copy = st.columns(2)
        col_csv.download_button(
            "Export CSV",
            data=df[["username", "url", "date"]].to_csv(index=False),
            file_name=f"{key}.csv",
            mime="text/csv",
            width="stretch",
            key=f"csv_{key}",
        )
        if col_copy.button("Copy usernames", key=f"cp_{key}", width="stretch"):
            st.code("\n".join(df["username"].tolist()), language=None)


# ── page header ───────────────────────────────────────────────────────────────

st.title("Instagram Non-Followers")
st.caption(
    "Built for the follow/unfollow growth loop: follow a batch of people, come back in a few days, "
    "unfollow the ones who didn't follow back, repeat — no login needed."
)

st.divider()


# ── sidebar: settings + ignore-list backup ──────────────────────────────────

with st.sidebar:
    st.header("⚙️ Settings")
    grace_days = st.slider(
        "Grace period (days)",
        min_value=1, max_value=30, value=3,
        help="How long to wait after following someone before flagging them as an unfollow candidate.",
    )

    st.divider()
    st.subheader("Ignore list")
    ignored_count = len(st.session_state.ignore_state["usernames"])
    st.caption(
        f"{ignored_count} account{'s' if ignored_count != 1 else ''} marked as "
        "\"not expected to follow back\" (celebrities, brands, friends, etc). "
        "They're excluded from your unfollow candidates."
    )

    if not HAS_BROWSER_STORAGE:
        st.warning(
            "Auto-remember isn't active — install `streamlit-javascript` "
            "(`pip install -r requirements.txt`) so this list survives a page reload. "
            "The backup file below always works as a fallback.",
            icon="⚠️",
        )

    st.download_button(
        "⬇️ Download backup",
        data=json.dumps(st.session_state.ignore_state, indent=2),
        file_name="ig_ignore_list.json",
        mime="application/json",
        width="stretch",
        disabled=ignored_count == 0,
    )

    backup_upload = st.file_uploader(
        "⬆️ Restore / merge backup",
        type="json",
        key="ignore_backup_upload",
        help="Load a previously downloaded ig_ignore_list.json — useful on a new browser or device.",
    )
    if backup_upload is not None:
        content_hash = hash(backup_upload.getvalue())
        if st.session_state.get("_last_backup_hash") != content_hash:
            try:
                imported = json.loads(backup_upload.getvalue().decode("utf-8"))
                merged = core.merge_ignore_states(st.session_state.ignore_state, imported)
                st.session_state.ignore_state = merged
                st.session_state._last_backup_hash = content_hash
                st.session_state._ignore_dirty = True
                st.success(f"Merged — {len(merged['usernames'])} accounts now ignored.")
                st.rerun()
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                st.error(f"Couldn't read that backup file: {exc}")


# ── upload ────────────────────────────────────────────────────────────────────

col_a, col_b = st.columns(2)

followers_files = col_a.file_uploader(
    "Followers  (`followers_1.json`, `followers_2.json`, ...)",
    type="json",
    accept_multiple_files=True,
    help="Upload all followers_*.json files from your Instagram data export.",
)

following_files = col_b.file_uploader(
    "Following  (`following.json`, or `following_1.json`, `following_2.json`, ...)",
    type="json",
    accept_multiple_files=True,
    help="Upload following.json — or all following_1.json, following_2.json, ... if Instagram split it.",
)

with st.expander("How to export your Instagram data"):
    st.markdown("""
1. Instagram → **Settings** → **Your activity** → **Download your information**
2. Choose **Some of your information** → tick **Followers and following** → **Next**
3. Set format to **JSON** → **Download to device** → **Create files**
4. Instagram emails you a link — download + unzip it
5. Inside `followers_and_following/` you'll find:
   - `followers_1.json` (and `followers_2.json`, etc. if you have many followers)
   - `following.json`
    """)

if not (followers_files and following_files):
    st.info("Upload your followers and following files above to get started.", icon="📂")
    st.stop()


# ── parse ─────────────────────────────────────────────────────────────────────

try:
    followers: list[dict] = []
    for f in followers_files:
        followers.extend(core.parse_export(json.load(f)))

    following: list[dict] = []
    for f in following_files:
        following.extend(core.parse_export(json.load(f)))

except Exception as exc:
    st.error("Could not read those files — make sure they're from Instagram's JSON export.")
    with st.expander("Error details"):
        st.code(str(exc))
    st.stop()

if not followers and not following:
    st.warning("Both files appear to be empty.")
    st.stop()

diff = core.compute_diff(followers, following)
not_following_back = diff["not_following_back"]
you_dont_follow = diff["you_dont_follow"]
mutual_count = diff["mutual_count"]

ignored_usernames = st.session_state.ignore_state["usernames"]
pending, ignored_rows = core.split_by_ignore_list(not_following_back, ignored_usernames)
ready_now = sum(
    1 for r in pending
    if (d := core.days_waiting(r["timestamp"])) is not None and d >= grace_days
)

# Only treat this as a "new check" (compare + advance the snapshot) when the
# uploaded data actually changed — every button click elsewhere on the page
# reruns this same script top-to-bottom with the same uploaded files still
# attached, and re-diffing against the snapshot on every one of those would
# make "since last check" mean "since the last click."
export_signature = hash((frozenset(diff["followers_set"]), frozenset(diff["following_set"])))
if st.session_state.get("_last_export_signature") != export_signature:
    st.session_state.last_snapshot_diff = core.diff_since_snapshot(diff["followers_set"], st.session_state.snapshot_state)
    st.session_state.snapshot_state = core.update_snapshot(diff["followers_set"])
    st.session_state._last_export_signature = export_signature
    _save_snapshot_state_to_browser(st.session_state.snapshot_state)
snapshot_diff = st.session_state.get("last_snapshot_diff")


# ── metrics ───────────────────────────────────────────────────────────────────

st.divider()
m1, m2, m3 = st.columns(3)
m1.metric("Following", len(diff["following_set"]))
m2.metric("Followers", len(diff["followers_set"]))
m3.metric("Mutual", mutual_count)

n1, n2, n3 = st.columns(3)
n1.metric("Unfollow candidates", len(pending))
n2.metric("Ready to unfollow now", ready_now)
n3.metric("Marked as expected", len(ignored_rows))

if snapshot_diff is None:
    st.caption("📌 First check on this browser — upload again after your next export to see what changed.")
else:
    gained = snapshot_diff["new_followers"]
    lost = snapshot_diff["lost_followers"]
    if not gained and not lost:
        st.caption(f"No follower changes since your last check ({snapshot_diff['since']}).")
    else:
        with st.expander(
            f"📈 Since your last check ({snapshot_diff['since']}): "
            f"+{len(gained)} new follower{'s' if len(gained) != 1 else ''}, "
            f"{len(lost)} unfollowed you",
            expanded=bool(lost),
        ):
            if lost:
                st.markdown("**Unfollowed you:**")
                for u in lost:
                    st.markdown(f"- [{u}](https://www.instagram.com/{u}/)")
            if gained:
                st.markdown("**New followers:**")
                for u in gained:
                    st.markdown(f"- [{u}](https://www.instagram.com/{u}/)")

st.divider()


# ── results tabs ──────────────────────────────────────────────────────────────

tab1, tab2, tab3 = st.tabs([
    f"🎯 Unfollow candidates  ({len(pending)})",
    f"🙈 Marked as expected  ({len(ignored_rows)})",
    f"You don't follow back  ({len(you_dont_follow)})",
])

render_table(
    pending, tab1, "unfollow_candidates", "You followed on",
    grace_days=grace_days,
    action_label="Mark as expected — stop flagging",
    action_fn=mark_as_ignored,
    empty_message="Nobody's pending — everyone you follow either follows back or is marked as expected.",
)
render_table(
    ignored_rows, tab2, "marked_as_expected", "You followed on",
    grace_days=grace_days,
    action_label="Un-ignore — bring back to candidates",
    action_fn=unignore,
    empty_message="You haven't marked anyone as expected yet. Select accounts in the candidates "
                   "tab (celebrities, brands, friends you don't need a follow-back from) to keep "
                   "them out of your way for good.",
)
render_table(you_dont_follow, tab3, "you_dont_follow_back", "They followed on")

st.divider()
st.caption(
    "Your files are processed in memory for this session only and never saved to disk — "
    "not stored, not logged, not shared. The ignore list and your last follower snapshot "
    "are saved locally in your browser, never sent anywhere."
)
