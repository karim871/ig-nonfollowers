# ig-nonfollowers

Instagram shows you your follower count. It doesn't show you who's not in it.
This does.

No login. No password. You feed it a file Instagram already lets you export, and it tells you the truth.

**Try it live: [ig-nonfollowers-xr7zrhmmasjcekrkkmd8ny.streamlit.app](https://ig-nonfollowers-xr7zrhmmasjcekrkkmd8ny.streamlit.app/)**

Uploaded files are processed in memory for your session only and never written to disk — nothing is stored or logged. If you'd rather not send your export to a hosted app at all, run it locally instead (below) and it never leaves your machine.

---

## How it works

Instagram lets you download your own data. Inside that export are two JSON files: who follows you, and who you follow. This tool reads both, finds the gap, and puts it in front of you.

That's it.

---

## Run it locally

```bash
pip install streamlit pandas
streamlit run app.py
```

Opens at `http://localhost:8501`.

---

## Get your Instagram files

1. Instagram → **Settings** → **Your activity** → **Download your information**
2. **Some of your information** → check **Followers and following** → **JSON**
3. Instagram emails you a ZIP — unzip it
4. Inside `followers_and_following/` you'll find `followers_1.json` and `following.json`

Upload both in the app. Results are instant.

---

## Deploy (free)

[![Deploy on Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io)

Fork this repo, connect it at [share.streamlit.io](https://share.streamlit.io), done.

---

## Test

```bash
python test_parser.py
```
