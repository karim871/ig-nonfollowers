import streamlit as st
import json
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="IG Non-Followers",
    page_icon="📊",
    layout="centered",
)

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; max-width: 760px; }
    [data-testid="metric-container"] {
        background: #f7f8fa;
        border-radius: 10px;
        padding: 0.8rem 1rem;
    }
    [data-testid="stFileUploaderDropzone"] { min-height: 80px; }
</style>
""", unsafe_allow_html=True)


# ── parser ────────────────────────────────────────────────────────────────────

def parse_export(data: dict | list) -> list[dict]:
    """Accept both Instagram export shapes (list-at-root or dict-wrapped)."""
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
                "date": datetime.fromtimestamp(ts).strftime("%b %d, %Y") if ts else "—",
            })
    return result


# ── table component ───────────────────────────────────────────────────────────

def render_table(rows: list[dict], tab, key: str, date_label: str):
    with tab:
        if not rows:
            st.success("Nothing here — you're all good!")
            return

        df = pd.DataFrame(rows).sort_values("username", ignore_index=True)
        total = len(df)

        query = st.text_input(
            "Search",
            placeholder=f"Search {total} accounts...",
            key=f"q_{key}",
            label_visibility="collapsed",
        )
        if query:
            df = df[df["username"].str.contains(query, case=False, na=False)]
            st.caption(f"Showing {len(df)} of {total}")

        # url column configured as LinkColumn so usernames are clickable
        st.dataframe(
            df[["url", "date"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "url": st.column_config.LinkColumn(
                    "Username",
                    display_text=r"https://www\.instagram\.com/([^/]+)",
                    width="medium",
                ),
                "date": st.column_config.TextColumn(date_label, width="small"),
            },
        )

        col_csv, col_copy = st.columns(2)

        col_csv.download_button(
            "Export CSV",
            data=df[["username", "url", "date"]].to_csv(index=False),
            file_name=f"{key}.csv",
            mime="text/csv",
            use_container_width=True,
        )

        if col_copy.button("Copy usernames", key=f"cp_{key}", use_container_width=True):
            st.code("\n".join(df["username"].tolist()), language=None)


# ── page header ───────────────────────────────────────────────────────────────

st.title("Instagram Non-Followers")
st.caption("Find out who doesn't follow you back — private, no login needed")

st.divider()


# ── upload ────────────────────────────────────────────────────────────────────

col_a, col_b = st.columns(2)

followers_files = col_a.file_uploader(
    "Followers  (`followers_1.json`, `followers_2.json`, ...)",
    type="json",
    accept_multiple_files=True,
    help="Upload all followers_*.json files from your Instagram data export.",
)

following_file = col_b.file_uploader(
    "Following  (`following.json`)",
    type="json",
    accept_multiple_files=False,
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

if not (followers_files and following_file):
    st.info("Upload your followers and following files above to get started.", icon="📂")
    st.stop()


# ── parse ─────────────────────────────────────────────────────────────────────

try:
    followers: list[dict] = []
    for f in followers_files:
        followers.extend(parse_export(json.load(f)))

    following = parse_export(json.load(following_file))

except Exception as exc:
    st.error("Could not read those files — make sure they're from Instagram's JSON export.")
    with st.expander("Error details"):
        st.code(str(exc))
    st.stop()

if not followers and not following:
    st.warning("Both files appear to be empty.")
    st.stop()

followers_set = {u["username"] for u in followers}
following_set = {u["username"] for u in following}

not_following_back = [u for u in following if u["username"] not in followers_set]
you_dont_follow   = [u for u in followers if u["username"] not in following_set]
mutual_count      = len(followers_set & following_set)


# ── metrics ───────────────────────────────────────────────────────────────────

st.divider()
m1, m2, m3, m4 = st.columns(4)
m1.metric("Following",          len(following_set))
m2.metric("Followers",          len(followers_set))
m3.metric("Mutual",             mutual_count)
m4.metric("Not following back", len(not_following_back))
st.divider()


# ── results tabs ──────────────────────────────────────────────────────────────

tab1, tab2 = st.tabs([
    f"Don't follow you back  ({len(not_following_back)})",
    f"You don't follow back  ({len(you_dont_follow)})",
])

render_table(not_following_back, tab1, "not_following_back",  "You followed on")
render_table(you_dont_follow,    tab2, "you_dont_follow_back", "They followed on")

st.divider()
st.caption("No data is stored or transmitted. Everything runs in your browser.")
