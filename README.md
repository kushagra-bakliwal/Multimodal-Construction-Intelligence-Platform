# 🏗️ Multimodal Construction Intelligence Platform

SkillWallet Capstone — Project 1 (Generative AI | Real Estate Decision Support)

A Streamlit decision-support app that analyses construction site photos for PPE safety compliance, classifies concrete cracks with severity scores, estimates project cost and market valuation in INR, and provides weather-aware site protocols with an engineering chatbot.

## Features

| Page | What it does |
|------|--------------|
| 🛡️ Site Safety & PPE Audit | Upload a site photo. Get a safety score (0-100), compliance status, PPE checklist (helmets, high-vis vests, steel-toe boots, harnesses), and hazards with severity and remedies. Download the JSON report. |
| 🔍 Crack Diagnostics | Upload a wall or concrete photo. Get defect type, estimated width (mm), severity level and 0-100 score, root cause, repair protocol and urgency. |
| 📊 Planning & Valuation | Budget, capex incurred, market value (Lakhs/Crores), steel and cement requirements, milestone progress bar, and an AI concept render via Pollinations. |
| 🤖 Site Assistant & Advisory | Weather selector with dynamic safety alerts, plus a multi-turn construction engineering chatbot. |

## Demo mode

No API key? The app still works. Image analysis and chat fall back to built-in demo data, so it is safe to deploy and show without credentials. Paste a Google Gemini API key into the sidebar to switch on live multimodal analysis.

## Run locally

```bash
git clone <your-repo-url>
cd construction-intelligence-platform
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Requires Python 3.9+.

## Deploy on Streamlit Community Cloud

1. Push this repo to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) and click **New app**.
3. Select the repo, branch `main`, and main file `app.py`.
4. Deploy. No database or secrets are needed (users enter their own API key in the sidebar).

## Project structure

```
.
├── app.py                 # Streamlit application
├── requirements.txt       # Python dependencies
├── .streamlit/config.toml # Theme and server settings
├── .gitignore
└── README.md
```

## Tech stack

- Python 3.9+, Streamlit
- Google Gemini (`google-genai`, model set by `MODEL_NAME` in `app.py`)
- Pillow, Requests
- Pollinations API for concept renders
- JSON data contracts with schema validation

## Notes

- Cost, steel and cement figures are indicative rule-of-thumb estimates, not engineering or valuation advice.
- AI safety and crack results are decision support only. Always confirm with a qualified site safety officer or structural engineer.
- Gemini model names change over time. If live calls fail, update `MODEL_NAME` in `app.py`.
