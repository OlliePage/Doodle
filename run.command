#!/bin/bash
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Creating local Python environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate

if ! python -c "import streamlit, openai, PIL, reportlab, fitz, pypdf" >/dev/null 2>&1; then
  echo "Installing Doodle dependencies..."
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
fi

python -m streamlit run app.py
