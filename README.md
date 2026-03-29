# 🎴 Professor Stats — Pokemon TCG Statistics Agent

> **Track 1 Submission — Build and Deploy AI Agents using Gemini, ADK, and Cloud Run**

An AI agent that answers statistical questions about Pokemon Trading Card Game cards using real data. Built with Google ADK, Gemini 2.5 Flash, and deployed as a serverless container on Cloud Run.

**Live Demo:** `https://pokemon-tcg-agent-676289354133.us-central1.run.app`

---

## What It Does

Professor Stats is a question-answering agent specialized in Pokemon TCG statistics. You can ask it things like:

- *"What is the average HP of Fire-type cards?"*
- *"Give me descriptive statistics on Charizard cards"*
- *"Compare price distributions of Rare Holo vs Common cards"*
- *"What is the current competitive TCG meta?"*

The agent fetches **real card data** from the Pokemon TCG API, computes **proper descriptive statistics** (mean, median, std dev, IQR, skewness, CV), and explains the results in plain language — bridging Pokemon TCG and Statistics.

---

## Architecture

```
User (Browser / curl)
        │
        ▼
  Cloud Run (us-central1)
  ┌─────────────────────────────────────────┐
  │  FastAPI  (main.py)                     │
  │      │                                  │
  │      ▼                                  │
  │  Agentic Loop (google-genai SDK)        │
  │      │                                  │
  │      ├── Tool 1: calculate_descriptive_stats  (Function Tool)
  │      ├── Tool 2: serper_google_search         (Custom Search Tool)
  │      └── Tool 3: fetch_pokemon_cards          (Pokemon TCG API v2)
  │                                         │
  │  Gemini 2.5 Flash (Vertex AI)           │
  └─────────────────────────────────────────┘
```

### Why Stateless?
Cloud Run scales instances dynamically. Rather than managing shared session state across instances (which requires Redis or Firestore), each request carries its own full context — a clean agentic loop that creates no persistent state. This is simpler, cheaper, and perfectly suited to the one-turn Q&A use case.

---

## Tools

| # | Tool | Type | Purpose |
|---|------|------|---------|
| 1 | `calculate_descriptive_stats` | Function Tool (pure Python) | Computes mean, median, std dev, IQR, Q1/Q3, skewness, coefficient of variation |
| 2 | `serper_google_search` | Custom Function Tool (Serper.dev API) | Real-time Google search for TCG meta, news, tournament results |
| 3 | `fetch_pokemon_cards` | Third-party API Tool (pokemontcg.io) | Fetches real card data: HP, attack damage, retreat cost, rarity, market price |

---

## Project Structure

```
pokemon_tcg_agent/
├── main.py                      # FastAPI server + agentic loop (entrypoint)
├── Dockerfile                   # Container build config
├── requirements.txt             # Python dependencies
├── .dockerignore
├── .env                         # Local API keys (never committed)
└── pokemon_tcg_stats/
    ├── __init__.py              # ADK package marker
    └── agent.py                 # Tool definitions (stats, search, TCG API)
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Agent Framework | Google ADK (Agent Development Kit) |
| LLM | Gemini 2.5 Flash via Vertex AI |
| HTTP Server | FastAPI + Uvicorn |
| Tool 1 | Python `statistics` stdlib (Function Tool) |
| Tool 2 | Serper.dev Google Search API (Custom Function Tool) |
| Tool 3 | Pokemon TCG API v2 — pokemontcg.io (Third-party API) |
| Containerization | Docker (python:3.11-slim) |
| Deployment | Google Cloud Run (us-central1) |
| Build | Google Cloud Build + Artifact Registry |

---

## Local Setup

### Prerequisites
- Python 3.11+
- Google Cloud project with Vertex AI enabled
- Pokemon TCG API key → [pokemontcg.io](https://dev.pokemontcg.io)
- Serper API key → [serper.dev](https://serper.dev) (free tier: 2,500 searches/month)

### 1. Clone & create virtual environment
```bash
git clone https://github.com/<your-username>/pokemon-tcg-agent
cd pokemon-tcg-agent
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment variables
```bash
# pokemon_tcg_stats/.env
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_GENAI_USE_VERTEXAI=TRUE
POKEMON_TCG_API_KEY=your-pokemon-tcg-api-key
SERPER_API_KEY=your-serper-api-key
```

### 4. Run locally
```bash
python main.py
# Open http://localhost:8080
```

### 5. Test via curl
```bash
curl -X POST http://localhost:8080/run \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the average HP of Fire-type cards?"}'
```

---

## Deployment to Cloud Run

### Enable GCP APIs
```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  aiplatform.googleapis.com \
  compute.googleapis.com
```

### Create Service Account & bind IAM roles
```bash
gcloud iam service-accounts create pokemon-tcg-agent-sa \
  --display-name="Pokemon TCG Agent SA"

SA="pokemon-tcg-agent-sa@$PROJECT_ID.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA" --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA" --role="roles/run.invoker"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA" --role="roles/logging.logWriter"
```

### Build & deploy
```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"

gcloud builds submit --tag gcr.io/$PROJECT_ID/pokemon-tcg-agent .

gcloud run deploy pokemon-tcg-agent \
  --image gcr.io/$PROJECT_ID/pokemon-tcg-agent \
  --region $REGION \
  --allow-unauthenticated \
  --service-account "pokemon-tcg-agent-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=$REGION,GOOGLE_GENAI_USE_VERTEXAI=TRUE,POKEMON_TCG_API_KEY=<key>,SERPER_API_KEY=<key>"
```

---

## API Reference

### `GET /`
Returns the web UI (HTML) for interacting with Professor Stats in the browser.

### `POST /run`
Send a message to the agent and receive a response.

**Request:**
```json
{ "message": "What is the average HP of Water-type cards?" }
```

**Response:**
```json
{
  "response": "Based on 20 Water-type cards fetched...\n\nMean HP: 112.5\nMedian HP: 110.0\n...",
  "agent": "pokemon_tcg_statistics_agent"
}
```

---

## Key Lessons Learned

- **ADK `google_search` built-in cannot be mixed with `FunctionTool`** in the same agent — replaced with a custom Serper.dev function tool to avoid `INVALID_ARGUMENT` errors.
- **ADK `Runner` + `InMemorySessionService` has session lookup issues** when session lifecycle and runner scope don't align — resolved by bypassing ADK Runner entirely and implementing a direct agentic loop with `google-genai` SDK.
- **Vertex AI model names require an explicit version suffix** — `gemini-2.5-flash` not `gemini-2.0-flash` (deprecated for new projects as of March 2026).
- **Cloud Run stateless design** eliminates session persistence complexity — each request is fully self-contained.

---

## Author

**Rafi Fernanda Aldin**
Bachelor of Statistics — Data Science, Psychometrics & Cloud Data Systems
*"Turning Uncertainty Into Insight"*
