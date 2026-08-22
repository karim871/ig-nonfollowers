@echo off
cd /d "%~dp0"

if not exist .venv (
    echo Setting up (first run only)...
    py -m venv .venv
)

call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
streamlit run app.py
