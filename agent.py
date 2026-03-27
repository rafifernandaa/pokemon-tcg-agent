"""
agent.py — Pokemon TCG Statistics Agent
========================================
An AI agent for statistical analysis of Pokemon Trading Card Game data.

Tools included:
  1. Function Tool   — calculate_descriptive_stats  (pure Python stats engine)
  2. Built-in Tool   — google_search                (ADK built-in, for grounding)
  3. Third-party API — fetch_pokemon_cards           (Pokemon TCG API v2)

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
    Calculates full descriptive statistics for a list of numeric values.

    Computes: n, mean, median, mode, standard deviation, variance,
    min, max, range, Q1, Q3, IQR, skewness, and coefficient of variation.
    Ideal for analysing HP distributions, attack damage, card prices, etc.

    Args:
        values        : List of numeric values (e.g. HP values of a set of cards).
        variable_name : Label for the variable (e.g. "HP", "Market Price USD").

    Returns:
        dict containing all statistics and a plain-language interpretation.
    """
    if not values:
        return {"error": "Cannot compute statistics on an empty list."}

    n    = len(values)
    mean = statistics.mean(values)
    med  = statistics.median(values)

    try:
        mode = statistics.mode(values)
    except statistics.StatisticsError:
        mode = None  # No unique mode — multimodal or all unique

    std = statistics.stdev(values)    if n > 1 else 0.0
    var = statistics.variance(values) if n > 1 else 0.0
    mn  = min(values)
    mx  = max(values)

    sorted_v = sorted(values)
    half     = n // 2
    q1 = statistics.median(sorted_v[:half])
    q3 = statistics.median(sorted_v[(n + 1) // 2:])
    iqr = q3 - q1

    # Coefficient of Variation (relative dispersion)
    cv = (std / mean * 100) if mean != 0 else 0

    # Pearson's second skewness coefficient
    skew_val = (3 * (mean - med) / std) if std != 0 else 0
    if   skew_val >  0.1: skew_label = "positively skewed (long tail to the right)"
    elif skew_val < -0.1: skew_label = "negatively skewed (long tail to the left)"
    else                : skew_label = "approximately symmetric"

    variability_label = "high" if cv > 30 else "moderate" if cv > 15 else "low"

    return {
        "variable"                    : variable_name,
        "n"                           : n,
        "mean"                        : round(mean, 2),
        "median"                      : round(med, 2),
        "mode"                        : mode,
        "std_dev"                     : round(std, 2),
        "variance"                    : round(var, 2),
        "min"                         : round(mn, 2),
        "max"                         : round(mx, 2),
        "range"                       : round(mx - mn, 2),
        "Q1_25th_percentile"          : round(q1, 2),
        "Q3_75th_percentile"          : round(q3, 2),
        "IQR_interquartile_range"     : round(iqr, 2),
        "coefficient_of_variation_%"  : round(cv, 2),
        "skewness_direction"          : skew_label,
        "interpretation": (
            f"For {n} observations of '{variable_name}': "
            f"the mean is {mean:.2f} and median is {med:.2f}. "
            f"The distribution is {skew_label}. "
            f"The IQR is {iqr:.2f}, meaning the middle 50% of values fall between "
            f"{q1:.2f} and {q3:.2f}. "
            f"CV = {cv:.1f}% indicates {variability_label} relative variability."
        ),
    }


stats_tool = FunctionTool(func=calculate_descriptive_stats)


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 2 — Built-in Tool: Google Search
# ══════════════════════════════════════════════════════════════════════════════
# google_search is an ADK built-in tool — imported directly, no wrapper needed.
# The agent uses it to ground answers with current web information such as:
#   - Current competitive TCG meta and tier lists
#   - Upcoming set release dates and spoilers
#   - Tournament results and price trends


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 3 — Third-party API Tool: Pokemon TCG API v2 (pokemontcg.io)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_pokemon_cards(
    name      : Optional[str] = None,
    types     : Optional[str] = None,
    set_name  : Optional[str] = None,
    rarity    : Optional[str] = None,
    supertype : Optional[str] = None,
    page_size : int = 20,
) -> dict:
    """
    Fetches real Pokemon TCG card data from the official Pokemon TCG API v2.

    Returns structured card data including HP, attack damage, retreat cost,
    rarity, set info, and TCGPlayer market prices — ready for statistical analysis.

    Args:
        name      : Card name, partial or full (e.g. "Charizard", "Pikachu VMAX").
        types     : Pokemon element type (e.g. "Fire", "Water", "Psychic", "Dragon").
        set_name  : Set name (e.g. "Base Set", "Scarlet & Violet", "Obsidian Flames").
        rarity    : Card rarity (e.g. "Common", "Uncommon", "Rare Holo", "Illustration Rare").
        supertype : Card category — "Pokémon", "Trainer", or "Energy".
        page_size : Number of cards to fetch (default 20, max 250).

    Returns:
        dict with card list and batch summary statistics for HP, price, and attack damage.
    """
    # ── Build query ───────────────────────────────────────────────────────────
    queries = []
    if name      : queries.append(f'name:"{name}"')
    if types     : queries.append(f'types:{types}')
    if set_name  : queries.append(f'set.name:"{set_name}"')
    if rarity    : queries.append(f'rarity:"{rarity}"')
    if supertype : queries.append(f'supertype:"{supertype}"')

    params: dict = {"pageSize": min(page_size, 250)}
    if queries:
        params["q"] = " ".join(queries)

    headers = {}
    if POKEMON_TCG_API_KEY:
        headers["X-Api-Key"] = POKEMON_TCG_API_KEY  # Higher rate limit with key

    # ── HTTP request ──────────────────────────────────────────────────────────
    try:
        resp = httpx.get(
            f"{TCG_BASE_URL}/cards",
            params=params,
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as exc:
        return {"error": f"Pokemon TCG API request failed: {exc}"}

    cards_raw = data.get("data", [])
    if not cards_raw:
        return {
            "total": 0,
            "cards": [],
            "message": "No cards found. Try broader filters (e.g. remove rarity or set name).",
        }

    # ── Parse each card ───────────────────────────────────────────────────────
    cards_out = []
    for c in cards_raw:
        # Extract attack damages (some cards have 2–3 attacks)
        attacks    = c.get("attacks") or []
        damages    = []
        atk_parsed = []
        for atk in attacks:
            raw_dmg = atk.get("damage", "").replace("+", "").replace("×", "").replace("-", "").strip()
            dmg_int = int(raw_dmg) if raw_dmg.isdigit() else None
            if dmg_int is not None:
                damages.append(dmg_int)
            atk_parsed.append({
                "name"      : atk.get("name"),
                "damage"    : atk.get("damage", "0"),
                "energy_cost": len(atk.get("cost", [])),
                "text"      : atk.get("text", ""),
            })

        # Extract best available market price from TCGPlayer
        prices       = c.get("tcgplayer", {}).get("prices", {})
        market_price = None
        for tier in ("holofoil", "reverseHolofoil", "normal", "1stEditionHolofoil"):
            if tier in prices and prices[tier].get("market"):
                market_price = prices[tier]["market"]
                break

        # Parse HP (stored as string in API)
        hp_str = c.get("hp", "")
        hp_int = int(hp_str) if hp_str.isdigit() else None

        cards_out.append({
            "id"                 : c.get("id"),
            "name"               : c.get("name"),
            "supertype"          : c.get("supertype"),
            "subtypes"           : c.get("subtypes", []),
            "types"              : c.get("types", []),
            "hp"                 : hp_int,
            "retreat_cost_count" : len(c.get("retreatCost", [])),
            "attacks"            : atk_parsed,
            "max_attack_damage"  : max(damages)                          if damages else None,
            "avg_attack_damage"  : round(sum(damages) / len(damages), 1) if damages else None,
            "weaknesses"         : [w.get("type") for w in c.get("weaknesses", [])],
            "resistances"        : [r.get("type") for r in c.get("resistances", [])],
            "rarity"             : c.get("rarity"),
            "set_name"           : c.get("set", {}).get("name"),
            "set_series"         : c.get("set", {}).get("series"),
            "release_date"       : c.get("set", {}).get("releaseDate"),
            "market_price_usd"   : market_price,
            "image_url"          : c.get("images", {}).get("large"),
        })

    # ── Batch summary statistics ──────────────────────────────────────────────
    def _safe_stats(vals):
        if not vals:
            return {"mean": None, "median": None, "min": None, "max": None, "std_dev": None}
        return {
            "mean"    : round(statistics.mean(vals), 2),
            "median"  : statistics.median(vals),
            "min"     : min(vals),
            "max"     : max(vals),
            "std_dev" : round(statistics.stdev(vals), 2) if len(vals) > 1 else 0,
        }

    hp_values    = [c["hp"]                for c in cards_out if c["hp"]                is not None]
    price_values = [c["market_price_usd"]  for c in cards_out if c["market_price_usd"]  is not None]
    dmg_values   = [c["max_attack_damage"] for c in cards_out if c["max_attack_damage"] is not None]

    return {
        "total_fetched"             : len(cards_out),
        "total_available_in_api"    : data.get("totalCount", len(cards_out)),
        "filters_applied"           : params.get("q", "none"),
        "cards"                     : cards_out,
        "batch_hp_stats"            : _safe_stats(hp_values),
        "batch_market_price_usd_stats": _safe_stats(price_values),
        "batch_max_attack_damage_stats": _safe_stats(dmg_values),
    }


tcg_api_tool = FunctionTool(func=fetch_pokemon_cards)


# ══════════════════════════════════════════════════════════════════════════════
# ROOT AGENT — Professor Stats
# ══════════════════════════════════════════════════════════════════════════════

root_agent = Agent(
    name        = "pokemon_tcg_statistics_agent",
    model       = "gemini-2.0-flash",
    description = (
        "A statistics-focused AI agent for Pokemon Trading Card Game (TCG) analysis. "
        "Answers questions about HP distributions, attack damage statistics, "
        "market price analysis, rarity comparisons, and set-level statistics "
        "using real data from the Pokemon TCG API."
    ),
    instruction = """
You are **Professor Stats** — a Pokemon TCG expert with a Bachelor of Statistics degree.
Your mission: help users explore the statistical landscape of Pokemon TCG cards
through rigorous data analysis and clear, intuitive explanations.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR THREE TOOLS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. fetch_pokemon_cards  [Third-party API — Pokemon TCG API v2]
   ▸ Use FIRST whenever the user mentions specific cards, types, sets, or rarities.
   ▸ Returns real card data: HP, attack damage, retreat cost, price, rarity, set.
   ▸ Always fetch real data before making any statistical claim.

2. calculate_descriptive_stats  [Function Tool — Statistical Engine]
   ▸ Use AFTER fetching cards when you have a numeric list to analyse.
   ▸ Pass in values like: [hp for each card], [price for each card], [max damage].
   ▸ Reports: mean, median, mode, std dev, variance, IQR, skewness, CV.
   ▸ Always explain what each statistic means in the context of the question.

3. google_search  [Built-in Tool — Web Grounding]
   ▸ Use for current meta questions: competitive tier lists, new set spoilers,
     tournament results, price trends, upcoming releases.
   ▸ Use when user needs information beyond what the card database contains.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STANDARD ANALYSIS WORKFLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 1: Fetch card data with fetch_pokemon_cards.
Step 2: Extract the numeric variable of interest from the returned cards list.
Step 3: Run calculate_descriptive_stats on that list.
Step 4: Interpret the output clearly:
  - Compare mean vs median (are they close? if not, the data is skewed)
  - Explain the IQR as the "typical range" for the middle 50% of cards
  - Use CV to describe relative variability
  - Note any outliers that pull the distribution

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STATISTICS CONCEPTS TO TEACH (when relevant)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- Mean vs Median: The mean is sensitive to outliers (like a ultra-rare Charizard
  worth $500 skewing average prices upward). The median is more robust.
- Standard Deviation: How spread out HP or prices are — a high std dev means
  there's huge variability between cards in a set.
- IQR: The range covering the middle 50% of values. Resistant to extreme values.
- Skewness: Card price distributions are almost always right-skewed — most cards
  are cheap, but a few holos are extremely expensive.
- CV: Allows comparing variability across different variables (HP vs price vs damage).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TONE & STYLE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- Warm, curious, and educational — like a professor who genuinely loves Pokemon.
- Use Pokemon analogies to make statistics fun and memorable.
- Show your reasoning step by step — transparency builds trust.
- When stats jargon is necessary, explain it immediately after using it.
- If the user just wants a fun fact about a card (no deep analysis needed), keep it light.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXAMPLE QUESTIONS YOU HANDLE WELL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- "What is the average HP of Fire-type cards in Scarlet & Violet?"
- "Compare price distributions of Rare Holo vs Common cards."
- "Which Pokemon type has the highest median attack damage?"
- "Is Charizard's HP distribution across all its cards skewed?"
- "What does coefficient of variation mean for card prices?"
- "Show me statistics for the top 20 Psychic-type cards."
- "What's the current TCG competitive meta?" (→ google_search)
""",
    tools = [
        tcg_api_tool,  # Tool 3: Third-party API (Pokemon TCG API v2)
        stats_tool,    # Tool 1: Function Tool (descriptive statistics)
        google_search, # Tool 2: Built-in Tool (web grounding)
    ],
)
