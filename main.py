"""
main.py — Pokemon TCG Statistics Agent (Session-free)
======================================================
Calls the agent tools directly without ADK session management.
Fully stateless — works perfectly on Cloud Run.
"""

import os
import logging
import uvicorn

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from google import genai
from google.genai import types

from pokemon_tcg_stats.agent import (
    calculate_descriptive_stats,
    fetch_pokemon_cards,
    serper_google_search,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(title="Pokemon TCG Statistics Agent — Professor Stats")

# ── Gemini client ─────────────────────────────────────────────────────────────

USE_VERTEX = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "FALSE").upper() == "TRUE"

if USE_VERTEX:
    client = genai.Client(
        vertexai=True,
        project=os.getenv("GOOGLE_CLOUD_PROJECT"),
        location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
    )
else:
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

MODEL = "gemini-2.5-flash"

# ── Tool declarations for Gemini function calling ─────────────────────────────

TOOLS = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="fetch_pokemon_cards",
            description="Fetch Pokemon TCG card data (HP, attacks, price, rarity) from pokemontcg.io.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "name"     : types.Schema(type=types.Type.STRING),
                    "types"    : types.Schema(type=types.Type.STRING),
                    "set_name" : types.Schema(type=types.Type.STRING),
                    "rarity"   : types.Schema(type=types.Type.STRING),
                    "supertype": types.Schema(type=types.Type.STRING),
                    "page_size": types.Schema(type=types.Type.INTEGER),
                },
            ),
        ),
        types.FunctionDeclaration(
            name="calculate_descriptive_stats",
            description="Compute mean, median, std dev, IQR, skewness, CV for a list of numbers.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "values"       : types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.NUMBER)),
                    "variable_name": types.Schema(type=types.Type.STRING),
                },
                required=["values"],
            ),
        ),
        types.FunctionDeclaration(
            name="serper_google_search",
            description="Search Google for current Pokemon TCG meta, news, and tournament results.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "query": types.Schema(type=types.Type.STRING),
                },
                required=["query"],
            ),
        ),
    ])
]

SYSTEM_INSTRUCTION = """You are Professor Stats — a Pokemon TCG expert with a Statistics degree.
Answer questions about Pokemon TCG cards using your tools.

TOOLS:
- fetch_pokemon_cards: get real card data (HP, damage, price, rarity)
- calculate_descriptive_stats: compute statistics on a list of numbers
- serper_google_search: search for current meta, news, tournament results

WORKFLOW for statistical questions:
1. Call fetch_pokemon_cards to get real data
2. Extract numeric values (HP, damage, price) from the cards list
3. Call calculate_descriptive_stats on those values
4. Explain results clearly using Pokemon analogies

Be warm, educational, and fun."""

# ── Tool dispatcher ───────────────────────────────────────────────────────────

def dispatch_tool(name: str, args: dict):
    if name == "fetch_pokemon_cards":
        return fetch_pokemon_cards(**args)
    elif name == "calculate_descriptive_stats":
        return calculate_descriptive_stats(**args)
    elif name == "serper_google_search":
        return serper_google_search(**args)
    return {"error": f"Unknown tool: {name}"}

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def ui():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Professor Stats — Pokemon TCG Agent</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, sans-serif; background: #0f1117; color: #e2e8f0; min-height: 100vh; display: flex; flex-direction: column; align-items: center; padding: 40px 16px; }
  h1 { font-size: 1.6rem; font-weight: 700; color: #fbbf24; margin-bottom: 4px; }
  p.sub { color: #94a3b8; font-size: 0.9rem; margin-bottom: 32px; }
  .card { background: #1e2330; border: 1px solid #2d3748; border-radius: 12px; padding: 24px; width: 100%; max-width: 720px; }
  textarea { width: 100%; background: #0f1117; border: 1px solid #2d3748; border-radius: 8px; color: #e2e8f0; font-size: 0.95rem; padding: 12px; resize: vertical; min-height: 100px; outline: none; }
  textarea:focus { border-color: #fbbf24; }
  button { margin-top: 12px; width: 100%; padding: 12px; background: #fbbf24; color: #0f1117; font-weight: 700; font-size: 1rem; border: none; border-radius: 8px; cursor: pointer; transition: opacity .2s; }
  button:hover { opacity: .85; }
  button:disabled { opacity: .5; cursor: not-allowed; }
  .examples { margin-top: 12px; display: flex; flex-wrap: wrap; gap: 8px; }
  .chip { background: #2d3748; border: none; color: #94a3b8; font-size: 0.78rem; padding: 6px 12px; border-radius: 20px; cursor: pointer; transition: background .2s; }
  .chip:hover { background: #3d4f63; color: #e2e8f0; }
  .response-box { margin-top: 24px; display: none; }
  .response-box h2 { font-size: 0.8rem; text-transform: uppercase; letter-spacing: .08em; color: #64748b; margin-bottom: 10px; }
  .response-text { background: #0f1117; border: 1px solid #2d3748; border-radius: 8px; padding: 16px; font-size: 0.92rem; line-height: 1.7; white-space: pre-wrap; color: #e2e8f0; }
  .spinner { display: inline-block; width: 18px; height: 18px; border: 2px solid #0f1117; border-top-color: transparent; border-radius: 50%; animation: spin .7s linear infinite; vertical-align: middle; margin-right: 8px; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .error { color: #f87171; }
</style>
</head>
<body>
<h1>🎴 Professor Stats</h1>
<p class="sub">Pokemon TCG Statistics Agent — powered by Gemini + ADK</p>
<div class="card">
  <textarea id="msg" placeholder="Ask me anything about Pokemon TCG cards…"></textarea>
  <div class="examples">
    <button class="chip" onclick="fill('What is the average HP of Fire-type cards?')">Avg HP of Fire-type</button>
    <button class="chip" onclick="fill('Give me stats on Charizard cards')">Charizard stats</button>
    <button class="chip" onclick="fill('Compare price distribution of Rare Holo vs Common cards')">Price distribution</button>
    <button class="chip" onclick="fill('What is the current Pokemon TCG competitive meta?')">Current meta</button>
    <button class="chip" onclick="fill('Which type has the highest median attack damage?')">Highest damage type</button>
  </div>
  <button id="btn" onclick="ask()">Ask Professor Stats</button>
  <div class="response-box" id="resp">
    <h2>Response</h2>
    <div class="response-text" id="resp-text"></div>
  </div>
</div>
<script>
function fill(text) {
  document.getElementById('msg').value = text;
  document.getElementById('msg').focus();
}
async function ask() {
  const msg = document.getElementById('msg').value.trim();
  if (!msg) return;
  const btn = document.getElementById('btn');
  const respBox = document.getElementById('resp');
  const respText = document.getElementById('resp-text');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Thinking…';
  respBox.style.display = 'block';
  respText.className = 'response-text';
  respText.textContent = 'Professor Stats is analysing your question…';
  try {
    const res = await fetch('/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Unknown error');
    respText.textContent = data.response;
  } catch (e) {
    respText.classList.add('error');
    respText.textContent = 'Error: ' + e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Ask Professor Stats';
  }
}
document.getElementById('msg').addEventListener('keydown', e => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) ask();
});
</script>
</body>
</html>"""


@app.post("/run")
async def run_agent(request: Request):
    body    = await request.json()
    message = body.get("message", "").strip()

    if not message:
        return JSONResponse(status_code=400, content={"error": "'message' is required."})

    log.info(f"Message: {message[:100]}")

    # Agentic loop — keep calling Gemini until no more tool calls
    contents = [types.Content(role="user", parts=[types.Part(text=message)])]

    try:
        for _ in range(10):  # max 10 tool-call rounds
            response = client.models.generate_content(
                model    = MODEL,
                contents = contents,
                config   = types.GenerateContentConfig(
                    system_instruction = SYSTEM_INSTRUCTION,
                    tools              = TOOLS,
                    temperature        = 0.2,
                ),
            )

            candidate = response.candidates[0]
            contents.append(types.Content(role="model", parts=candidate.content.parts))

            # Check if there are tool calls to execute
            tool_calls = [p for p in candidate.content.parts if p.function_call]
            if not tool_calls:
                # No tool calls — this is the final text response
                final_text = "".join(
                    p.text for p in candidate.content.parts if hasattr(p, "text") and p.text
                )
                log.info("Final response ready")
                return {"response": final_text, "agent": "pokemon_tcg_statistics_agent"}

            # Execute all tool calls and feed results back
            tool_results = []
            for part in tool_calls:
                fc   = part.function_call
                result = dispatch_tool(fc.name, dict(fc.args))
                log.info(f"Tool called: {fc.name}")
                tool_results.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            name    = fc.name,
                            response= {"result": result},
                        )
                    )
                )
            contents.append(types.Content(role="user", parts=tool_results))

        return {"response": "Max tool rounds reached.", "agent": "pokemon_tcg_statistics_agent"}

    except Exception as exc:
        log.error(f"Error: {exc}")
        return JSONResponse(status_code=500, content={"error": str(exc)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")
