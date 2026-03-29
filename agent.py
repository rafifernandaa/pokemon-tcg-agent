"""
pokemon_tcg_stats/agent.py — Agent definition only.
HTTP serving is handled by main.py at the project root.

Tools:
  1. Function Tool   — calculate_descriptive_stats
  2. Function Tool   — serper_google_search (custom search via serper.dev)
  3. Third-party API — fetch_pokemon_cards (pokemontcg.io)

Multi-agent architecture (required because google_search built-in
cannot be mixed with FunctionTools in Gemini API):
  root_agent
  ├── data_agent   → tcg_api_tool + stats_tool
  └── search_agent → serper_tool
"""

import os
import json
import statistics
from typing import Optional

import httpx
from dotenv import load_dotenv

from google.adk.agents import Agent
from google.adk.tools import FunctionTool

load_dotenv()

POKEMON_TCG_API_KEY = os.getenv("POKEMON_TCG_API_KEY", "")
SERPER_API_KEY      = os.getenv("SERPER_API_KEY", "")
TCG_BASE_URL        = "https://api.pokemontcg.io/v2"


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 1 — Function Tool: Descriptive Statistics Calculator
# ══════════════════════════════════════════════════════════════════════════════

def calculate_descriptive_stats(
    values: list[float],
    variable_name: str = "variable",
) -> dict:
    """
    Calculates full descriptive statistics for a list of numeric values.

    Computes: n, mean, median, mode, std dev, variance, min, max, range,
    Q1, Q3, IQR, coefficient of variation, and skewness direction.
    Use this after fetching card data to analyse HP, attack damage, or prices.

    Args:
        values        : List of numeric values (e.g. HP values of cards).
        variable_name : Label for the variable being analysed.

    Returns:
        dict with all statistics and a plain-language interpretation.
    """
    if not values:
        return {"error": "Cannot compute statistics on an empty list."}

    n    = len(values)
    mean = statistics.mean(values)
    med  = statistics.median(values)

    try:
        mode = statistics.mode(values)
    except statistics.StatisticsError:
        mode = None

    std = statistics.stdev(values)    if n > 1 else 0.0
    var = statistics.variance(values) if n > 1 else 0.0
    mn  = min(values)
    mx  = max(values)

    sorted_v = sorted(values)
    half     = n // 2
    q1  = statistics.median(sorted_v[:half])
    q3  = statistics.median(sorted_v[(n + 1) // 2:])
    iqr = q3 - q1
    cv  = (std / mean * 100) if mean != 0 else 0

    skew_val = (3 * (mean - med) / std) if std != 0 else 0
    if   skew_val >  0.1: skew_label = "positively skewed (tail to the right)"
    elif skew_val < -0.1: skew_label = "negatively skewed (tail to the left)"
    else                : skew_label = "approximately symmetric"

    variability = "high" if cv > 30 else "moderate" if cv > 15 else "low"

    return {
        "variable"                  : variable_name,
        "n"                         : n,
        "mean"                      : round(mean, 2),
        "median"                    : round(med, 2),
        "mode"                      : mode,
        "std_dev"                   : round(std, 2),
        "variance"                  : round(var, 2),
        "min"                       : round(mn, 2),
        "max"                       : round(mx, 2),
        "range"                     : round(mx - mn, 2),
        "Q1_25th_percentile"        : round(q1, 2),
        "Q3_75th_percentile"        : round(q3, 2),
        "IQR"                       : round(iqr, 2),
        "coefficient_of_variation_%": round(cv, 2),
        "skewness"                  : skew_label,
        "interpretation": (
            f"For {n} '{variable_name}' values: mean={mean:.2f}, median={med:.2f}. "
            f"Distribution is {skew_label}. "
            f"Middle 50% falls between {q1:.2f} and {q3:.2f} (IQR={iqr:.2f}). "
            f"CV={cv:.1f}% → {variability} relative variability."
        ),
    }


stats_tool = FunctionTool(func=calculate_descriptive_stats)


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 2 — Function Tool: Custom Google Search via Serper.dev
# (Replaces ADK built-in google_search to avoid the multi-tool conflict)
# ══════════════════════════════════════════════════════════════════════════════

def serper_google_search(query: str) -> str:
    """
    Searches Google for real-time information using the Serper.dev API.
    Use for competitive TCG meta, tournament results, price trends, new sets.

    Args:
        query : Search query string (e.g. "Pokemon TCG Scarlet Violet meta 2025").

    Returns:
        Formatted string with top 5 search result titles, links, and snippets.
    """
    if not SERPER_API_KEY:
        return "Error: SERPER_API_KEY not found in environment variables."

    try:
        resp = httpx.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            content=json.dumps({"q": query, "num": 5}),
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json()

        snippets = []
        for r in results.get("organic", [])[:5]:
            snippets.append(
                f"Title  : {r.get('title', 'N/A')}\n"
                f"Link   : {r.get('link', 'N/A')}\n"
                f"Snippet: {r.get('snippet', 'N/A')}"
            )

        return "\n---\n".join(snippets) if snippets else "No results found."

    except Exception as exc:
        return f"Search failed: {exc}"


serper_tool = FunctionTool(func=serper_google_search)


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 3 — Third-party API: Pokemon TCG API v2 (pokemontcg.io)
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
    Fetches Pokemon TCG card data from the official Pokemon TCG API v2.
    Returns HP, attack damage, retreat cost, rarity, set, and market price.

    Args:
        name      : Card name (e.g. "Charizard", "Pikachu VMAX").
        types     : Pokemon type (e.g. "Fire", "Water", "Psychic").
        set_name  : Set name (e.g. "Scarlet & Violet", "Obsidian Flames").
        rarity    : Rarity (e.g. "Common", "Rare Holo", "Illustration Rare").
        supertype : "Pokémon", "Trainer", or "Energy".
        page_size : Cards to fetch (default 20, max 250).

    Returns:
        dict with card list and batch summary stats for HP, price, and damage.
    """
    queries = []
    if name      : queries.append(f'name:"{name}"')
    if types     : queries.append(f'types:{types}')
    if set_name  : queries.append(f'set.name:"{set_name}"')
    if rarity    : queries.append(f'rarity:"{rarity}"')
    if supertype : queries.append(f'supertype:"{supertype}"')

    params  = {"pageSize": min(page_size, 250)}
    if queries:
        params["q"] = " ".join(queries)

    headers = {"X-Api-Key": POKEMON_TCG_API_KEY} if POKEMON_TCG_API_KEY else {}

    try:
        resp = httpx.get(
            f"{TCG_BASE_URL}/cards",
            params=params, headers=headers, timeout=15,
        )
        resp.raise_for_status()
        raw  = resp.json()
        data = raw.get("data", [])
    except Exception as exc:
        return {"error": str(exc)}

    if not data:
        return {"total": 0, "cards": [], "message": "No cards found for these filters."}

    cards_out = []
    for c in data:
        # Parse HP
        hp_val = int(c["hp"]) if c.get("hp", "").isdigit() else None

        # Parse attacks
        attacks = c.get("attacks") or []
        damages = []
        atk_out = []
        for a in attacks:
            raw_dmg = a.get("damage", "").replace("+","").replace("×","").replace("-","").strip()
            dmg_int = int(raw_dmg) if raw_dmg.isdigit() else None
            if dmg_int: damages.append(dmg_int)
            atk_out.append({
                "name"       : a.get("name"),
                "damage"     : a.get("damage", "0"),
                "energy_cost": len(a.get("cost", [])),
            })

        # Parse market price
        prices = c.get("tcgplayer", {}).get("prices", {})
        m_price = None
        for tier in ("holofoil", "reverseHolofoil", "normal", "1stEditionHolofoil"):
            if tier in prices and prices[tier].get("market"):
                m_price = prices[tier]["market"]
                break

        cards_out.append({
            "name"               : c.get("name"),
            "hp"                 : hp_val,
            "types"              : c.get("types", []),
            "rarity"             : c.get("rarity"),
            "set_name"           : c.get("set", {}).get("name"),
            "attacks"            : atk_out,
            "max_attack_damage"  : max(damages) if damages else None,
            "avg_attack_damage"  : round(sum(damages)/len(damages),1) if damages else None,
            "retreat_cost_count" : len(c.get("retreatCost", [])),
            "market_price_usd"   : m_price,
        })

    def _s(vals):
        if not vals:
            return {"mean": None, "median": None, "min": None, "max": None}
        return {
            "mean"  : round(statistics.mean(vals), 2),
            "median": statistics.median(vals),
            "min"   : min(vals),
            "max"   : max(vals),
        }

    hp_vals    = [c["hp"]               for c in cards_out if c["hp"]               is not None]
    price_vals = [c["market_price_usd"] for c in cards_out if c["market_price_usd"] is not None]
    dmg_vals   = [c["max_attack_damage"]for c in cards_out if c["max_attack_damage"]is not None]

    return {
        "total_fetched"           : len(cards_out),
        "total_in_api"            : raw.get("totalCount", len(cards_out)),
        "cards"                   : cards_out,
        "batch_hp_stats"          : _s(hp_vals),
        "batch_price_usd_stats"   : _s(price_vals),
        "batch_max_damage_stats"  : _s(dmg_vals),
    }


tcg_api_tool = FunctionTool(func=fetch_pokemon_cards)


# ══════════════════════════════════════════════════════════════════════════════
# MULTI-AGENT ARCHITECTURE
# data_agent   → Tool 1 (stats) + Tool 3 (TCG API)   — no search built-in
# search_agent → Tool 2 (serper search)               — custom FunctionTool
# root_agent   → orchestrator only, no direct tools
# ══════════════════════════════════════════════════════════════════════════════

data_agent = Agent(
    name        = "data_agent",
    model       = "gemini-2.5-flash",
    description = (
        "Fetches real Pokemon TCG card data and performs descriptive statistical "
        "analysis (mean, median, std dev, IQR, skewness, CV) on HP, attack damage, "
        "market prices, and other numeric attributes."
    ),
    instruction = """
You are a data analysis specialist for Pokemon TCG cards.

WORKFLOW:
1. Call fetch_pokemon_cards with appropriate filters to get real card data.
2. Extract the numeric variable of interest (HP, max_attack_damage, market_price_usd).
3. Call calculate_descriptive_stats on that list of values.
4. Interpret the statistics clearly — explain mean vs median, IQR, skewness, and CV
   using Pokemon analogies where helpful.

Always show your reasoning step by step.
""",
    tools = [tcg_api_tool, stats_tool],
)

search_agent = Agent(
    name        = "search_agent",
    model       = "gemini-2.5-flash",
    description = (
        "Searches the web for current Pokemon TCG news, competitive meta, "
        "tournament results, upcoming sets, and price trends."
    ),
    instruction = """
You are a Pokemon TCG news and meta specialist.

Use serper_google_search to find current information about:
- Competitive TCG format and tier lists
- Recent tournament results and top decklists
- Upcoming set releases and card spoilers
- Card price trends and market news

Always mention the source title and link in your response.
""",
    tools = [serper_tool],
)

root_agent = Agent(
    name        = "pokemon_tcg_statistics_agent",
    model       = "gemini-2.5-flash",
    description = (
        "Professor Stats — Pokemon TCG expert with a Statistics degree. "
        "Answers statistical questions about cards and stays current on the meta."
    ),
    instruction = """
You are Professor Stats — a Pokemon TCG expert with a Bachelor of Statistics degree.
You orchestrate two specialist sub-agents.

ROUTING:
→ data_agent   : card statistics, HP analysis, price distributions, attack damage,
                 rarity comparisons, descriptive stats of any card attribute.
→ search_agent : current competitive meta, tournament news, upcoming sets,
                 anything requiring real-time web information.

After receiving results from a sub-agent:
- Synthesise into a clear, friendly explanation.
- Explain statistical terms in plain language.
- Use Pokemon analogies to make stats fun and intuitive.
- Be warm and educational — like a professor who loves Pokemon.
""",
    sub_agents = [data_agent, search_agent],
)
