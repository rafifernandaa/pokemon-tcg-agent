# 🎴 Pokemon TCG Statistics Agent
**Track 1 — Build and Deploy AI Agents using Gemini, ADK, and Cloud Run**

An AI agent (Professor Stats) that answers statistical questions about Pokemon
Trading Card Game data. Built with Google ADK + Gemini 2.0 Flash, deployed on Cloud Run.

---

## Architecture

```
User Query
    │
    ▼
Cloud Run ─── ADK Agent (Professor Stats)
                    │
        ┌───────────┼────────────────┐
        ▼           ▼                ▼
  fetch_pokemon  calculate_      google_search
  _cards         descriptive_    (Built-in)
  (TCG API v2)   stats
  [3rd-party]    [Function Tool]
```

## Tools

| # | Tool | Type | Purpose |
|---|------|------|---------|
| 1 | `calculate_descriptive_stats` | Function Tool | Computes mean, median, std dev, IQR, skewness, CV on any numeric list |
| 2 | `google_search` | ADK Built-in | Grounds answers with current web data (meta, prices, tournament results) |
| 3 | `fetch_pokemon_cards` | Third-party API | Fetches real card data from pokemontcg.io (HP, damage, price, rarity) |

---

## Quick Start

### Prerequisites
- Python 3.11+
- Google Cloud project with billing enabled
- Gemini API key (https://aistudio.google.com/)
- Pokemon TCG API key (https://pokemontcg.io/) — free!

---

## Step-by-Step Setup

### 1. Create Project Directory
```bash
mkdir pokemon_tcg_agent
cd pokemon_tcg_agent
```

### 2. Create & Activate Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows
```

### 3. Install Google ADK
```bash
pip install --upgrade pip
pip install google-adk
```

### 4. Scaffold Agent with `adk create`
```bash
adk create pokemon_tcg_stats
# This generates:
# pokemon_tcg_stats/
# ├── agent.py
# ├── __init__.py
# └── .env
```

### 5. Replace Agent Files
Copy the files from this repo into `pokemon_tcg_stats/`:
- `agent.py` — Agent definition with all 3 tools
- `__init__.py` — ADK package marker
- `.env` — Your API keys (fill in your values)

### 6. Fill in `.env`
```bash
# pokemon_tcg_stats/.env
GOOGLE_API_KEY=your-gemini-api-key
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=asia-southeast2
GOOGLE_GENAI_USE_VERTEXAI=FALSE
POKEMON_TCG_API_KEY=your-pokemon-tcg-api-key
```

### 7. Install All Dependencies
```bash
pip install -r requirements.txt
```

### 8. Run the Agent Locally
```bash
# Option A: Terminal chat
adk run pokemon_tcg_stats

# Option B: Web UI (recommended for demo)
adk web
# Open: http://localhost:8000
```

---

## Deploy to Cloud Run

### Enable GCP APIs
```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="asia-southeast2"

gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  aiplatform.googleapis.com \
  compute.googleapis.com \
  --project=$PROJECT_ID
```

### Create Service Account & Bind IAM Roles
```bash
# Create service account
gcloud iam service-accounts create pokemon-tcg-agent-sa \
  --display-name="Pokemon TCG Agent Service Account" \
  --project=$PROJECT_ID

SA_EMAIL="pokemon-tcg-agent-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# Bind required roles
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.invoker"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/logging.logWriter"
```

### Deploy with ADK (Recommended)
```bash
adk deploy cloud_run \
  --project=$PROJECT_ID \
  --region=$REGION \
  --service_name=pokemon-tcg-agent \
  --app_name=pokemon_tcg_stats \
  --with_ui \
  --service_account="${SA_EMAIL}"
```

### Get Your Service URL
```bash
gcloud run services describe pokemon-tcg-agent \
  --region=$REGION \
  --format='value(status.url)'
```

---

## Example Queries

```
"What is the average HP of Fire-type Pokemon cards in Scarlet & Violet?"
"Compare the price distribution of Rare Holo vs Common cards."
"Which Pokemon type has the highest median attack damage?"
"Is the HP distribution of Charizard cards skewed?"
"What does the coefficient of variation tell us about card prices?"
"Give me descriptive statistics for the top 20 Psychic-type cards."
"What's the current Pokemon TCG competitive meta?"
```

---

## Project Structure

```
pokemon_tcg_agent/
├── .venv/                        ← virtual environment (not committed)
├── pokemon_tcg_stats/
│   ├── __init__.py               ← ADK package marker
│   ├── agent.py                  ← Agent + 3 tools (main file)
│   └── .env                      ← API keys (never commit!)
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Agent Framework | Google ADK (Agent Development Kit) |
| LLM | Gemini 2.0 Flash |
| Tool 1 | Python `statistics` module (Function Tool) |
| Tool 2 | ADK `google_search` built-in |
| Tool 3 | Pokemon TCG API v2 via `httpx` (Third-party) |
| Deployment | Google Cloud Run |
| Region | asia-southeast2 (Jakarta) |

---

## Cleanup
```bash
gcloud run services delete pokemon-tcg-agent --region=$REGION
```
