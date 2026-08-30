@echo off
cd /d %~dp0
if not exist .venv (
  py -m venv .venv
)
call .venv\Scripts\activate
python -c "import streamlit, openai, PIL, reportlab, fitz, pypdf" >nul 2>&1
if errorlevel 1 (
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
)
python -m streamlit run app.py
