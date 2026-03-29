# 🎴 Pokemon TCG Statistics Agent — Professor Stats
**Track 1 — Build and Deploy AI Agents using Gemini, ADK, and Cloud Run**

An AI agent that answers statistical questions about Pokemon Trading Card Game data.
Built with Google ADK + Gemini 2.0 Flash, deployed as a serverless REST API on Cloud Run.

**Live endpoint:** `https://pokemon-tcg-agent-676289354133.us-central1.run.app`

---

## Architecture

```
POST /run  {"message": "..."}
        │
        ▼
  FastAPI (main.py)
        │
        ▼
  Gemini 2.0 Flash ──► root_agent (orchestrator)
                              │
               ┌──────────────┴──────────────┐
               ▼                             ▼
         data_agent                    search_agent
         ├── fetch_pokemon_cards        └── serper_google_search
         │   (Pokemon TCG API v2)           (Serper.dev / Google)
         └── calculate_descriptive_stats
             (Python statistics module)
```

---

## Tools

| # | Tool | Type | Purpose |
|---|------|------|---------|
| 1 | `calculate_descriptive_stats` | Function Tool | Mean, median, std dev, IQR, skewness, CV |
| 2 | `serper_google_search` | Function Tool (3rd-party) | Current TCG meta, news, tournament results |
| 3 | `fetch_pokemon_cards` | Function Tool (3rd-party API) | Live card data from pokemontcg.io |

---

## Prerequisites

- Python 3.11+
- `gcloud` CLI installed and authenticated
- Google Cloud project with billing enabled
- Gemini API key → https://aistudio.google.com/app/apikey
- Pokemon TCG API key (free) → https://dev.pokemontcg.io
- Serper API key (free tier) → https://serper.dev

---

## Local Development

### Step 1 — Clone the repo

```bash
git clone https://github.com/your-username/pokemon-tcg-agent.git
cd pokemon-tcg-agent
```

### Step 2 — Create virtual environment

```bash
python3 -m venv .venv
```

### Step 3 — Activate virtual environment

```bash
# Linux / macOS / Cloud Shell
source .venv/bin/activate

# Windows (Command Prompt)
.venv\Scripts\activate.bat

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

You should see `(.venv)` at the start of your terminal prompt.

### Step 4 — Upgrade pip and install Google ADK

```bash
pip install --upgrade pip
pip install google-adk
```

### Step 5 — Scaffold ADK project with `adk create`

```bash
adk create pokemon_tcg_stats
```

This generates the required ADK package structure:

```
pokemon_tcg_stats/
├── agent.py       ← define your agent here
├── __init__.py    ← ADK package marker
└── .env           ← API keys and config
```

### Step 6 — Replace generated files with project files

Copy the files from this repo into `pokemon_tcg_stats/`:

```bash
cp agent.py pokemon_tcg_stats/agent.py
cp __init__.py pokemon_tcg_stats/__init__.py
```

### Step 7 — Fill in `pokemon_tcg_stats/.env`

```bash
# Google Cloud / Vertex AI
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_GENAI_USE_VERTEXAI=TRUE

# OR use Gemini Developer API (simpler for local testing)
# GOOGLE_GENAI_USE_VERTEXAI=FALSE
# GOOGLE_API_KEY=your-gemini-api-key

# Pokemon TCG API — free key at https://dev.pokemontcg.io
POKEMON_TCG_API_KEY=your-pokemon-tcg-api-key

# Serper.dev — free tier at https://serper.dev
SERPER_API_KEY=your-serper-api-key
```

> ⚠️ Never commit `.env` to Git — it is already listed in `.gitignore`

### Step 8 — Install all dependencies

```bash
pip install -r requirements.txt
```

---

## Running Locally

### Option A — Terminal chat with `adk run`

Runs the agent directly in your terminal as an interactive chat session.

```bash
adk run pokemon_tcg_stats
```

Example session:
```
You: What is the average HP of Fire-type cards?
Agent: I'll fetch the data first...
[fetches cards → computes stats]
The average HP of Fire-type cards is 112.4, with a median of 110...
```

Type `exit` or press `Ctrl+C` to quit.

### Option B — Web UI with `adk web` (recommended for demo)

Launches a browser-based chat interface at `http://localhost:8000`.

```bash
adk web
```

Then open your browser and go to:
```
http://localhost:8000
```

Select `pokemon_tcg_stats` from the agent dropdown and start chatting.

---

## Deploy to Cloud Run

### Step 1 — Set environment variables

```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"
export SERVICE_NAME="pokemon-tcg-agent"
export SA_NAME="pokemon-tcg-agent-sa"
export SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
```

### Step 2 — Enable required GCP APIs

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  aiplatform.googleapis.com \
  compute.googleapis.com \
  --project=$PROJECT_ID
```

### Step 3 — Create service account

```bash
gcloud iam service-accounts create $SA_NAME \
  --display-name="Pokemon TCG Agent Service Account" \
  --project=$PROJECT_ID
```

### Step 4 — Bind IAM roles to service account

```bash
# Vertex AI — to call Gemini
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/aiplatform.user"

# Cloud Run Invoker — for service-to-service auth
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.invoker"

# Logs Writer — write to Cloud Logging
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/logging.logWriter"
```

### Step 5 — Build container image with Cloud Build

```bash
gcloud builds submit \
  --tag gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --project=$PROJECT_ID
```

This uses the `Dockerfile` in the project root to build and push the image
to Google Container Registry.

### Step 6 — Deploy to Cloud Run

```bash
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --max-instances 3 \
  --memory 512Mi \
  --timeout 120 \
  --service-account $SA_EMAIL \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION},GOOGLE_GENAI_USE_VERTEXAI=TRUE,POKEMON_TCG_API_KEY=your-pokemon-tcg-api-key,SERPER_API_KEY=your-serper-api-key" \
  --project=$PROJECT_ID
```

### Step 7 — Get your service URL

```bash
gcloud run services describe $SERVICE_NAME \
  --region $REGION \
  --format='value(status.url)'
```

Output example:
```
https://pokemon-tcg-agent-676289354133.us-central1.run.app
```

### Step 8 — Test the deployed agent

```bash
export SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
  --region $REGION --format='value(status.url)')

# Health check
curl $SERVICE_URL/

# Ask Professor Stats a question
curl -X POST $SERVICE_URL/run \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the average HP of Fire-type cards?"}'
```

Expected response:
```json
{
  "response": "Based on 20 Fire-type cards fetched: the average HP is 112.4, median is 110.0, std dev is 28.3...",
  "agent": "pokemon_tcg_statistics_agent"
}
```

---

## API Reference

### `GET /`
Health check.

**Response:**
```json
{"status": "ok", "agent": "pokemon_tcg_statistics_agent", "model": "gemini-2.0-flash-001"}
```

### `POST /run`
Send a message to Professor Stats.

**Request body:**
```json
{"message": "Your question here"}
```

**Response:**
```json
{"response": "Agent's answer...", "agent": "pokemon_tcg_statistics_agent"}
```

**Example questions:**
```
"What is the average HP of Fire-type cards in Scarlet & Violet?"
"Compare price distributions of Rare Holo vs Common cards."
"Which Pokemon type has the highest median attack damage?"
"Is the HP distribution of Charizard cards skewed?"
"What does coefficient of variation mean for card prices?"
"What's the current Pokemon TCG competitive meta?"
```

---

## Project Structure

```
pokemon-tcg-agent/
├── main.py                    ← FastAPI entrypoint (Cloud Run)
├── Dockerfile                 ← Container build config
├── requirements.txt           ← Python dependencies
├── .gitignore
├── README.md
└── pokemon_tcg_stats/         ← ADK agent package
    ├── __init__.py            ← ADK package marker
    ├── agent.py               ← Agent + 3 tools definition
    └── .env                   ← API keys (never commit!)
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Agent Framework | Google ADK (Agent Development Kit) |
| LLM | Gemini 2.0 Flash 001 via Vertex AI |
| Tool 1 | Python `statistics` module — Function Tool |
| Tool 2 | Serper.dev Google Search — Function Tool |
| Tool 3 | Pokemon TCG API v2 (`pokemontcg.io`) — Function Tool |
| HTTP Server | FastAPI + Uvicorn |
| Deployment | Google Cloud Run |
| Container Registry | Google Container Registry (GCR) |
| Build | Google Cloud Build |

---

## Deactivate / Cleanup

```bash
# Deactivate virtual environment
deactivate

# Delete Cloud Run service
gcloud run services delete $SERVICE_NAME --region=$REGION

# Delete container image
gcloud container images delete gcr.io/$PROJECT_ID/$SERVICE_NAME --force-delete-tags
```
