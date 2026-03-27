#!/usr/bin/env bash
# =============================================================================
# setup.sh  —  Full setup script for Pokemon TCG Statistics Agent
# Track 1: Build and Deploy AI Agents using Gemini, ADK, and Cloud Run
#
# Usage:
#   chmod +x setup.sh
#   ./setup.sh
# =============================================================================

set -euo pipefail

# ─── COLOUR OUTPUT ────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
section() { echo -e "\n${BOLD}${GREEN}═══ $* ═══${RESET}\n"; }

# ─── USER CONFIG — fill these before running ──────────────────────────────────
PROJECT_ID="your-gcp-project-id"          # e.g. my-pokemon-agent-123
REGION="asia-southeast2"                   # Jakarta region
SERVICE_NAME="pokemon-tcg-agent"
POKEMON_TCG_API_KEY="your-pokemon-tcg-api-key"   # https://pokemontcg.io/
GOOGLE_API_KEY="your-gemini-api-key"             # https://aistudio.google.com/
# ─────────────────────────────────────────────────────────────────────────────

section "STEP 1 — Create Project Directory"
PROJECT_DIR="pokemon_tcg_agent"
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"
success "Directory '$PROJECT_DIR' created"

# ─────────────────────────────────────────────────────────────────────────────
section "STEP 2 — Create & Activate Virtual Environment"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
success "venv created and activated at .venv/"

# ─────────────────────────────────────────────────────────────────────────────
section "STEP 3 — Install Google ADK"
pip install --quiet --upgrade pip
pip install --quiet google-adk
success "google-adk installed"

# ─────────────────────────────────────────────────────────────────────────────
section "STEP 4 — Scaffold Agent with 'adk create'"
# adk create generates: agent.py, __init__.py, .env inside a sub-folder
adk create pokemon_tcg_stats
success "ADK project scaffold created"

# ─────────────────────────────────────────────────────────────────────────────
section "STEP 5 — Write Agent Files"

# ── .env ─────────────────────────────────────────────────────────────────────
cat > pokemon_tcg_stats/.env << ENV
# Google AI / Vertex AI
GOOGLE_API_KEY=${GOOGLE_API_KEY}
GOOGLE_CLOUD_PROJECT=${PROJECT_ID}
GOOGLE_CLOUD_LOCATION=${REGION}
GOOGLE_GENAI_USE_VERTEXAI=FALSE

# Pokemon TCG API (https://pokemontcg.io/)
POKEMON_TCG_API_KEY=${POKEMON_TCG_API_KEY}
ENV
success ".env written"

# ── __init__.py ───────────────────────────────────────────────────────────────
cat > pokemon_tcg_stats/__init__.py << 'INIT'
"""
Pokemon TCG Statistics Agent package.
ADK discovers the agent via this file.
"""
from . import agent
INIT
success "__init__.py written"

# ── agent.py ──────────────────────────────────────────────────────────────────
cat > pokemon_tcg_stats/agent.py << 'AGENTPY'
"""
agent.py — Pokemon TCG Statistics Agent
========================================
An AI agent for statistical analysis of Pokemon Trading Card Game data.

Tools used:
  1. Function Tool   — calculate_descriptive_stats (pure Python stats)
  2. Built-in Tool   — google_search (grounding / meta queries)
  3. Third-party API — fetch_pokemon_cards (Pokemon TCG API v2)

Author  : Rafi Fernanda Aldin
Major   : Bachelor of Statistics
Track   : 1 — Build and Deploy AI Agents using Gemini, ADK, and Cloud Run
"""

import os
import statistics
from typing import Optional

import httpx
from dotenv import load_dotenv

from google.adk.agents import Agent
from google.adk.tools import FunctionTool, google_search

load_dotenv()

POKEMON_TCG_API_KEY = os.getenv("POKEMON_TCG_API_KEY", "")
TCG_BASE_URL        = "https://api.pokemontcg.io/v2"

# ══════════════════════════════════════════════════════════════════════════════
# TOOL 1 — Function Tool: Descriptive Statistics Calculator
# ══════════════════════════════════════════════════════════════════════════════

def calculate_descriptive_stats(values: list[float], variable_name: str = "variable") -> dict:
    """
    Calculates descriptive statistics for a list of numeric values.

    Computes: n, mean, median, mode, std dev, variance, min, max, range,
    Q1, Q3, IQR, skewness direction, and coefficient of variation (CV).
    Useful for analysing HP distributions, attack damage, card prices, etc.

    Args:
        values        : List of numeric values (e.g. HP values of cards).
        variable_name : Label for the variable being analysed (e.g. "HP").

    Returns:
        dict with all descriptive statistics and a plain-language interpretation.
    """
    if not values:
        return {"error": "Cannot compute statistics on an empty list."}

    n    = len(values)
    mean = statistics.mean(values)
    med  = statistics.median(values)

    try:
        mode = statistics.mode(values)
    except statistics.StatisticsError:
        mode = None  # no unique mode

    std  = statistics.stdev(values)  if n > 1 else 0
    var  = statistics.variance(values) if n > 1 else 0
    mn   = min(values)
    mx   = max(values)

    sorted_v = sorted(values)
    q1 = statistics.median(sorted_v[:n // 2])
    q3 = statistics.median(sorted_v[(n + 1) // 2:])
    iqr = q3 - q1

    cv = (std / mean * 100) if mean != 0 else 0

    # Simple skewness direction (Pearson's 2nd coefficient approximation)
    skew_val = 3 * (mean - med) / std if std != 0 else 0
    if skew_val > 0.1:
        skew_dir = "positively skewed (tail to the right)"
    elif skew_val < -0.1:
        skew_dir = "negatively skewed (tail to the left)"
    else:
        skew_dir = "approximately symmetric"

    return {
        "variable"              : variable_name,
        "n"                     : n,
        "mean"                  : round(mean, 2),
        "median"                : round(med, 2),
        "mode"                  : mode,
        "std_dev"               : round(std, 2),
        "variance"              : round(var, 2),
        "min"                   : mn,
        "max"                   : mx,
        "range"                 : round(mx - mn, 2),
        "Q1"                    : round(q1, 2),
        "Q3"                    : round(q3, 2),
        "IQR"                   : round(iqr, 2),
        "coefficient_of_variation_%": round(cv, 2),
        "skewness"              : skew_dir,
        "interpretation": (
            f"The {variable_name} of {n} cards has a mean of {mean:.1f} "
            f"and median of {med:.1f}. The distribution is {skew_dir}. "
            f"CV = {cv:.1f}% indicates "
            f"{'high' if cv > 30 else 'moderate' if cv > 15 else 'low'} variability."
        ),
    }


stats_tool = FunctionTool(func=calculate_descriptive_stats)


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 2 — Built-in Tool: Google Search (grounding)
# ══════════════════════════════════════════════════════════════════════════════
# google_search is an ADK built-in tool — no extra code needed.
# The agent uses it to answer meta-questions like:
#   "What is the current Pokemon TCG meta?"
#   "Which set has the highest average card price?"


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 3 — Third-party API Tool: Pokemon TCG API v2
# ══════════════════════════════════════════════════════════════════════════════

def fetch_pokemon_cards(
    name        : Optional[str] = None,
    types       : Optional[str] = None,
    set_name    : Optional[str] = None,
    rarity      : Optional[str] = None,
    supertype   : Optional[str] = None,
    page_size   : int = 20,
) -> dict:
    """
    Fetches Pokemon TCG cards from the official Pokemon TCG API v2 (pokemontcg.io).
    Returns card data including HP, attack damage, retreat cost, and market price.

    Args:
        name       : Partial or full card name (e.g. "Charizard", "Pikachu").
        types      : Pokemon type filter (e.g. "Fire", "Water", "Psychic").
        set_name   : Set name filter (e.g. "Base Set", "Scarlet & Violet").
        rarity     : Rarity filter (e.g. "Rare Holo", "Common", "Uncommon").
        supertype  : Card category — "Pokémon", "Trainer", or "Energy".
        page_size  : Max number of cards to return (default 20, max 250).

    Returns:
        dict with list of cards, each containing stats useful for analysis.
    """
    # Build query string
    queries = []
    if name:       queries.append(f'name:"{name}"')
    if types:      queries.append(f'types:{types}')
    if set_name:   queries.append(f'set.name:"{set_name}"')
    if rarity:     queries.append(f'rarity:"{rarity}"')
    if supertype:  queries.append(f'supertype:"{supertype}"')

    params: dict = {"pageSize": min(page_size, 250)}
    if queries:
        params["q"] = " ".join(queries)

    headers = {}
    if POKEMON_TCG_API_KEY:
        headers["X-Api-Key"] = POKEMON_TCG_API_KEY

    try:
        resp = httpx.get(f"{TCG_BASE_URL}/cards", params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as exc:
        return {"error": f"Pokemon TCG API request failed: {exc}"}

    cards_raw = data.get("data", [])
    if not cards_raw:
        return {"total": 0, "cards": [], "message": "No cards found for the given filters."}

    # Extract relevant statistical fields
    cards_out = []
    for c in cards_raw:
        # Aggregate attack damage (some cards have multiple attacks)
        attacks = c.get("attacks") or []
        damages = []
        for atk in attacks:
            dmg_str = atk.get("damage", "").replace("+", "").replace("×", "").replace("-", "")
            if dmg_str.isdigit():
                damages.append(int(dmg_str))

        # Market price from TCGPlayer
        prices = c.get("tcgplayer", {}).get("prices", {})
        market_price = None
        for tier in ("holofoil", "reverseHolofoil", "normal", "1stEditionHolofoil"):
            if tier in prices and prices[tier].get("market"):
                market_price = prices[tier]["market"]
                break

        cards_out.append({
            "id"            : c.get("id"),
            "name"          : c.get("name"),
            "supertype"     : c.get("supertype"),
            "subtypes"      : c.get("subtypes", []),
            "types"         : c.get("types", []),
            "hp"            : int(c["hp"]) if c.get("hp", "").isdigit() else None,
            "retreat_cost"  : len(c.get("retreatCost", [])),
            "attacks"       : [
                {
                    "name"         : a.get("name"),
                    "damage"       : a.get("damage", "0"),
                    "cost_count"   : len(a.get("cost", [])),
                }
                for a in attacks
            ],
            "max_attack_damage" : max(damages) if damages else None,
            "avg_attack_damage" : round(sum(damages) / len(damages), 1) if damages else None,
            "weaknesses"    : [w.get("type") for w in c.get("weaknesses", [])],
            "rarity"        : c.get("rarity"),
            "set_name"      : c.get("set", {}).get("name"),
            "set_series"    : c.get("set", {}).get("series"),
            "market_price_usd": market_price,
            "image_url"     : c.get("images", {}).get("large"),
        })

    # Summary stats for HP and price across the fetched batch
    hp_values    = [c["hp"]               for c in cards_out if c["hp"] is not None]
    price_values = [c["market_price_usd"] for c in cards_out if c["market_price_usd"] is not None]
    dmg_values   = [c["max_attack_damage"] for c in cards_out if c["max_attack_damage"] is not None]

    return {
        "total_fetched"       : len(cards_out),
        "total_available"     : data.get("totalCount", len(cards_out)),
        "cards"               : cards_out,
        "batch_hp_stats": {
            "mean"  : round(statistics.mean(hp_values), 1)   if hp_values else None,
            "median": statistics.median(hp_values)            if hp_values else None,
            "min"   : min(hp_values)                          if hp_values else None,
            "max"   : max(hp_values)                          if hp_values else None,
        },
        "batch_price_stats_usd": {
            "mean"  : round(statistics.mean(price_values), 2) if price_values else None,
            "median": statistics.median(price_values)          if price_values else None,
            "min"   : min(price_values)                        if price_values else None,
            "max"   : max(price_values)                        if price_values else None,
        },
        "batch_max_damage_stats": {
            "mean"  : round(statistics.mean(dmg_values), 1)  if dmg_values else None,
            "median": statistics.median(dmg_values)           if dmg_values else None,
            "min"   : min(dmg_values)                         if dmg_values else None,
            "max"   : max(dmg_values)                         if dmg_values else None,
        },
    }


tcg_api_tool = FunctionTool(func=fetch_pokemon_cards)


# ══════════════════════════════════════════════════════════════════════════════
# ROOT AGENT
# ══════════════════════════════════════════════════════════════════════════════

root_agent = Agent(
    name        = "pokemon_tcg_statistics_agent",
    model       = "gemini-2.0-flash",
    description = (
        "A statistics-focused AI agent for Pokemon Trading Card Game analysis. "
        "Answers questions about card HP distributions, attack damage statistics, "
        "market price analysis, rarity breakdowns, and comparative set statistics."
    ),
    instruction = """
You are Professor Stats — a Pokemon TCG expert with a Statistics degree.
Your job is to help users explore and understand the statistical properties
of Pokemon TCG cards through data analysis and clear explanations.

## Your Tools
1. **fetch_pokemon_cards** (Pokemon TCG API):
   - Use this FIRST whenever the user asks about specific cards, sets, types, or rarities.
   - Always fetch real data before making statistical claims.
   - Extract HP values, attack damage, prices, retreat cost for analysis.

2. **calculate_descriptive_stats** (Statistical Calculator):
   - Use this AFTER fetching cards to compute proper statistics.
   - Always call this when you have a list of numeric values (HP, damage, price).
   - Report: mean, median, std dev, IQR, skewness, CV — explain each clearly.

3. **google_search** (Web Search):
   - Use for meta questions: current TCG format, tournament results, upcoming sets.
   - Use when the user asks about real-world context beyond card data.

## How to Answer Questions
When a user asks a statistical question:
1. Fetch relevant cards using `fetch_pokemon_cards`.
2. Extract the numeric variable of interest (HP, price, damage).
3. Run `calculate_descriptive_stats` on that list.
4. Interpret the results in plain language, like a statistician explaining to a non-statistician.

## Statistics Concepts to Explain
- **Mean vs Median**: Explain which is more appropriate (especially when data is skewed).
- **Standard Deviation**: How spread out the values are.
- **IQR**: The middle 50% range — robust to outliers.
- **Skewness**: Whether rare high-HP or high-price cards pull the distribution.
- **CV (Coefficient of Variation)**: Relative variability — useful for comparing HP vs damage.

## Tone
- Friendly, curious, and educational.
- Use Pokemon analogies to make statistics fun.
- Always show your reasoning step by step.
- If asked a non-TCG statistics question, still answer helpfully.

## Example Queries You Handle
- "What is the average HP of Fire-type Pokemon cards in Scarlet & Violet?"
- "Compare the price distribution of Rare Holo vs Common cards."
- "Which Pokemon type has the highest median attack damage?"
- "Is Charizard's HP distribution skewed?"
- "What does standard deviation mean in the context of card prices?"
""",
    tools = [
        tcg_api_tool,     # Tool 3: Third-party API
        stats_tool,        # Tool 1: Function Tool
        google_search,     # Tool 2: Built-in Tool
    ],
)
AGENTPY
success "agent.py written"

# ─────────────────────────────────────────────────────────────────────────────
section "STEP 6 — Install Full Requirements"
pip install --quiet google-adk httpx python-dotenv
success "All packages installed"

# ─────────────────────────────────────────────────────────────────────────────
section "STEP 7 — Write requirements.txt"
cat > requirements.txt << 'REQ'
google-adk>=0.3.0
google-genai>=1.0.0
httpx>=0.27.0
python-dotenv>=1.0.0
REQ
success "requirements.txt written"

# ─────────────────────────────────────────────────────────────────────────────
section "STEP 8 — Test Agent Locally (choose one)"
echo ""
info "Option A — Terminal chat:"
echo "   adk run pokemon_tcg_stats"
echo ""
info "Option B — Web UI (recommended for demo):"
echo "   adk web"
echo "   Then open: http://localhost:8000"
echo ""
warn "Make sure your .env has valid API keys before running!"

# ─────────────────────────────────────────────────────────────────────────────
section "STEP 9 — Enable GCP APIs"
echo ""
info "Run this block in your terminal (requires gcloud CLI + authenticated account):"
cat << 'GCPAPIS'

gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  aiplatform.googleapis.com \
  compute.googleapis.com \
  --project=${PROJECT_ID}

GCPAPIS

# ─────────────────────────────────────────────────────────────────────────────
section "STEP 10 — Create Service Account & Bind IAM Roles"
cat << 'GCPIAM'

# Create dedicated service account for the agent
gcloud iam service-accounts create pokemon-tcg-agent-sa \
  --display-name="Pokemon TCG Agent Service Account" \
  --project=${PROJECT_ID}

SA_EMAIL="pokemon-tcg-agent-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant required IAM roles
# Vertex AI User — to call Gemini via Vertex AI
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/aiplatform.user"

# Cloud Run Invoker — if using service-to-service auth
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.invoker"

# Logs Writer — so the agent can write to Cloud Logging
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/logging.logWriter"

GCPIAM
success "IAM commands printed above — run them in your terminal"

# ─────────────────────────────────────────────────────────────────────────────
section "STEP 11 — Deploy to Cloud Run with ADK"
cat << 'GCPDEPLOY'

# Deploy using ADK's built-in Cloud Run deployment command
adk deploy cloud_run \
  --project=${PROJECT_ID} \
  --region=${REGION} \
  --service_name=pokemon-tcg-agent \
  --app_name=pokemon_tcg_stats \
  --with_ui \
  --service_account="pokemon-tcg-agent-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# --- OR: Manual deploy via Dockerfile ---

# 1. Create Artifact Registry repo
gcloud artifacts repositories create pokemon-tcg-agent-repo \
  --repository-format=docker \
  --location=${REGION} \
  --project=${PROJECT_ID}

# 2. Build image
gcloud builds submit \
  --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/pokemon-tcg-agent-repo/pokemon-tcg-agent:latest \
  --project=${PROJECT_ID}

# 3. Deploy to Cloud Run
gcloud run deploy pokemon-tcg-agent \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/pokemon-tcg-agent-repo/pokemon-tcg-agent:latest \
  --region ${REGION} \
  --platform managed \
  --allow-unauthenticated \
  --service-account "pokemon-tcg-agent-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --set-env-vars "GOOGLE_API_KEY=${GOOGLE_API_KEY},POKEMON_TCG_API_KEY=${POKEMON_TCG_API_KEY},GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION}" \
  --memory 512Mi \
  --timeout 120 \
  --project=${PROJECT_ID}

GCPDEPLOY

# ─────────────────────────────────────────────────────────────────────────────
section "DONE! Summary"
echo ""
echo "  Project structure:"
echo "  pokemon_tcg_agent/"
echo "  ├── .venv/                  ← virtual environment"
echo "  ├── pokemon_tcg_stats/"
echo "  │   ├── __init__.py         ← ADK package marker"
echo "  │   ├── agent.py            ← Agent + 3 tools"
echo "  │   └── .env                ← API keys (DO NOT commit)"
echo "  └── requirements.txt"
echo ""
success "Setup complete! Fill in your API keys in pokemon_tcg_stats/.env then run:"
info "  source .venv/bin/activate && adk web"
