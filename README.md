# ig-nonfollowers

A tool for the follow/unfollow growth loop: follow a batch of accounts, come back
in a few days, unfollow the ones that didn't follow back, repeat.

No login. No password. You feed it a file Instagram already lets you export,
and it tells you the truth.

**Try it live: [ig-nonfollowers-xr7zrhmmasjcekrkkmd8ny.streamlit.app](https://ig-nonfollowers-xr7zrhmmasjcekrkkmd8ny.streamlit.app/)**

Uploaded files are processed in memory for your session only and never written
to disk — nothing is stored or logged. If you'd rather not send your export to
a hosted app at all, run it locally instead (below) and it never leaves your
machine.

---

## The workflow

1. Go follow a batch of accounts on Instagram, same as you always would.
2. Wait a few days.
3. Export your Instagram data (below), upload it here.
4. The app splits everyone you follow who hasn't followed back into:
   - **Unfollow candidates** — people you followed, sorted by how long they've
     had a chance to follow back. Past your grace period, they're flagged
     🔴 *unfollow now*.
   - **Marked as expected** — accounts you've told the app not to bug you
     about (celebrities, brands, friends you followed for content, not for a
     follow-back). Select them once in the candidates tab and they're excluded
     from every future check.
5. Unfollow the 🔴 candidates on Instagram, go follow your next batch, repeat.

Every re-upload re-evaluates against your current ignore list, so the list you
actually need to act on stays legitimate: real people who should be following
you back and aren't.

Each time you upload, the app also remembers who followed you at that moment.
Next time you check, it automatically tells you who unfollowed you and who's
new since then — no manual comparison between exports required.

The app can't unfollow anyone for you — it never logs into Instagram, on
purpose. It gives you the exact, sorted list; you do the unfollowing in the
Instagram app.

---

## Run it locally

**Windows:** double-click `run.bat`
**Mac/Linux:** `./run.sh`

Either script sets up a virtual environment, installs dependencies, and
launches the app — first run does the setup, every run after that is instant.

Prefer to do it by hand:

```bash
pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501`.

---

## Get your Instagram files

1. Instagram → **Settings** → **Your activity** → **Download your information**
2. **Some of your information** → check **Followers and following** → **JSON**
3. Instagram emails you a ZIP — unzip it
4. Inside `followers_and_following/` you'll find `followers_1.json` and
   `following.json` (large accounts may see `followers_2.json`,
   `following_1.json`, etc. — Instagram splits large lists across files)

Upload all of them in the app. Results are instant.

---

## Your ignore list

Accounts you mark as "expected" (won't follow back, and that's fine) are
remembered two ways:

- **Automatically**, in your browser's local storage — nothing to do, it just
  sticks around next time you open the app in the same browser.
- **As a downloadable backup** — the sidebar has a "Download backup" button
  for `ig_ignore_list.json`. Use it to move your list to another browser or
  device (upload it there via "Restore / merge backup"), or just to keep a
  safe copy — it's a file you manage yourself, same as your Instagram export.

---

## Deploy your own hosted link (free)

Want a link you (or a friend) can open from any device with zero setup?

[![Deploy on Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io)

1. Fork this repo to your own GitHub account.
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click **New app**, pick your fork, branch `main`, main file `app.py`.
4. Deploy. You get a public URL — bookmark it and use it like any other app.

Since nothing is stored server-side, everyone who uses your deployed link gets
their own private session: uploads and ignore lists never mix between visitors
and disappear when the tab closes (the ignore list and your last follower
snapshot still persist per-browser via local storage; the ignore list can also
be backed up/restored with the JSON file above).

---

## Test

```bash
python test_parser.py
```

Covers the export parser, the follower/following diff, the wait-time
calculation, and the ignore-list logic (add/remove/merge) — all pure functions
in `core.py`, no Streamlit required to run them.
