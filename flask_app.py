from flask import Flask, request, render_template, session
from openai import OpenAI
import google.generativeai as genai
import requests
import os

app = Flask(__name__)
app.secret_key = 'boardchat2025rulez'

# === 6 AI MODELS CONFIG ===
AI_CONFIGS = {
    'openai': {
        'model': 'gpt-4o-mini',
        'client': lambda key: OpenAI(api_key=key),
        'generate': lambda client, prompt: client.chat.completions.create(
            model=AI_CONFIGS['openai']['model'],
            messages=[{"role": "user", "content": prompt}]
        ).choices[0].message.content
    },
    'gemini': {
        'model': 'gemini-1.5-flash',
        'client': lambda key: (genai.configure(api_key=key), genai.GenerativeModel(AI_CONFIGS['gemini']['model']))[1],
        'generate': lambda client, prompt: client.generate_content(prompt).text
    },
    'llama': {
        'model': 'meta-llama/llama-3.1-70b-instruct:free',
        'endpoint': 'https://openrouter.ai/api/v1/chat/completions',
        'generate': lambda key, prompt: requests.post(
            AI_CONFIGS['llama']['endpoint'],
            headers={'Authorization': f'Bearer {key}'},
            json={'model': AI_CONFIGS['llama']['model'], 'messages': [{'role': 'user', 'content': prompt}]}
        ).json()['choices'][0]['message']['content']
    },
    'claude': {
        'model': 'anthropic/claude-3.5-sonnet',
        'endpoint': 'https://openrouter.ai/api/v1/chat/completions',
        'generate': lambda key, prompt: requests.post(
            AI_CONFIGS['claude']['endpoint'],
            headers={'Authorization': f'Bearer {key}'},
            json={'model': AI_CONFIGS['claude']['model'], 'messages': [{'role': 'user', 'content': prompt}]}
        ).json()['choices'][0]['message']['content']
    },
    'deepseek': {
        'model': 'deepseek/deepseek-chat',
        'endpoint': 'https://openrouter.ai/api/v1/chat/completions',
        'generate': lambda key, prompt: requests.post(
            AI_CONFIGS['deepseek']['endpoint'],
            headers={'Authorization': f'Bearer {key}'},
            json={'model': AI_CONFIGS['deepseek']['model'], 'messages': [{'role': 'user', 'content': prompt}]}
        ).json()['choices'][0]['message']['content']
    },
    'grok': {
        'model': 'x-ai/grok-beta',
        'endpoint': 'https://openrouter.ai/api/v1/chat/completions',
        'generate': lambda key, prompt: requests.post(
            AI_CONFIGS['grok']['endpoint'],
            headers={'Authorization': f'Bearer {key}'},
            json={'model': AI_CONFIGS['grok']['model'], 'messages': [{'role': 'user', 'content': prompt}]}
        ).json()['choices'][0]['message']['content']
    }
}

# === HELPER FUNCTION ===
def run_boardroom(query, prompt_template):
    active_ais = {ai: cfg for ai, cfg in AI_CONFIGS.items() if session.get(f'{ai}_key')}
    if len(active_ais) < 2:
        return "Need 2+ API keys to run boardroom."

    responses = {}
    for ai, cfg in active_ais.items():
        try:
            key = session[f'{ai}_key']
            prompt = prompt_template.format(query=query)
            if 'endpoint' in cfg:
                resp = cfg['generate'](key, prompt)
            else:
                client = cfg['client'](key)
                resp = cfg['generate'](client, prompt)
            responses[ai] = resp
        except Exception as e:
            responses[ai] = f"Error from {ai.upper()}: {str(e)}"

    ai_list = list(responses.keys())
    numbered = "\n".join([f"{i+1}. {ai.upper()}: {responses[ai]}" for i, ai in enumerate(ai_list)])
    vote_prompt = f"Vote for the best answer:\n{numbered}\nReply ONLY with the number (1-{len(ai_list)})."

    votes = {i+1: 0 for i in range(len(ai_list))}
    for ai, cfg in active_ais.items():
        try:
            key = session[f'{ai}_key']
            if 'endpoint' in cfg:
                vote = cfg['generate'](key, vote_prompt)
            else:
                client = cfg['client'](key)
                vote = cfg['generate'](client, vote_prompt)
            num = int(vote.strip())
            if 1 <= num <= len(ai_list):
                votes[num] += 1
        except:
            pass

    best = max(votes, key=votes.get)
    winner = ai_list[best - 1].upper()
    return (
        f"**Boardroom Decision ({votes[best]} votes):** {winner} WINS!\n\n{responses[winner.lower()]}\n\n"
        f"---\n\n**All {len(ai_list)} Proposals:**\n" +
        "\n\n".join([f"**{ai.upper()}:**\n{resp}" for ai, resp in responses.items()])
    )

# === ROUTES ===
@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    ai_keys = {ai: session.get(f'{ai}_key', '') for ai in AI_CONFIGS}
    if request.method == 'POST':
        for ai in AI_CONFIGS:
            session[f'{ai}_key'] = request.form.get(f'{ai}_key', '').strip()
        query = request.form.get('query', '').strip()
        if query:
            result = run_boardroom(query, "{query}")
    return render_template('index.html', result=result, ai_keys=ai_keys)

@app.route('/idea_eval', methods=['GET', 'POST'])
def idea_eval():
    result = None
    ai_keys = {ai: session.get(f'{ai}_key', '') for ai in AI_CONFIGS}
    if request.method == 'POST':
        query = request.form.get('query', '').strip()
        if query:
            prompt = ("Evaluate this business idea: {query}\n"
                      "Include: pros, cons, market fit (1-10), revenue potential (USD/year). Be concise.")
            result = run_boardroom(query, prompt)
    return render_template('idea_eval.html', result=result, ai_keys=ai_keys)

@app.route('/market_research', methods=['GET', 'POST'])
def market_research():
    result = None
    ai_keys = {ai: session.get(f'{ai}_key', '') for ai in AI_CONFIGS}
    if request.method == 'POST':
        query = request.form.get('query', '').strip()
        if query:
            prompt = "Market research for: {query}\nKey trends, opportunities, challenges. Be concise."
            result = run_boardroom(query, prompt)
    return render_template('market_research.html', result=result, ai_keys=ai_keys)

@app.route('/competitive_analysis', methods=['GET', 'POST'])
def competitive_analysis():
    result = None
    ai_keys = {ai: session.get(f'{ai}_key', '') for ai in AI_CONFIGS}
    if request.method == 'POST':
        query = request.form.get('query', '').strip()
        if query:
            prompt = "Competitor analysis for: {query}\nStrengths, weaknesses, recommendations. Be concise."
            result = run_boardroom(query, prompt)
    return render_template('competitive_analysis.html', result=result, ai_keys=ai_keys)

@app.route('/financial_projections', methods=['GET', 'POST'])
def financial_projections():
    result = None
    ai_keys = {ai: session.get(f'{ai}_key', '') for ai in AI_CONFIGS}
    if request.method == 'POST':
        query = request.form.get('query', '').strip()
        if query:
            prompt = ("Financial projections for: {query}\n"
                      "Revenue, costs, profit (USD/year) for 3 years. Be concise.")
            result = run_boardroom(query, prompt)
    return render_template('financial_projections.html', result=result, ai_keys=ai_keys)

@app.route('/global_expansion', methods=['GET', 'POST'])
def global_expansion():
    result = None
    ai_keys = {ai: session.get(f'{ai}_key', '') for ai in AI_CONFIGS}
    if request.method == 'POST':
        query = request.form.get('query', '').strip()
        if query:
            prompt = ("Global expansion for: {query}\n"
                      "Target markets, entry strategy, costs (USD/year). Be concise.")
            result = run_boardroom(query, prompt)
    return render_template('global_expansion.html', result=result, ai_keys=ai_keys)

@app.route('/ai_ethics_audit', methods=['GET', 'POST'])
def ai_ethics_audit():
    result = None
    ai_keys = {ai: session.get(f'{ai}_key', '') for ai in AI_CONFIGS}
    if request.method == 'POST':
        query = request.form.get('query', '').strip()
        if query:
            prompt = ("AI ethics audit for: {query}\n"
                      "Risks, compliance, mitigation. Be concise.")
            result = run_boardroom(query, prompt)
    return render_template('ai_ethics_audit.html', result=result, ai_keys=ai_keys)

@app.route('/rd_breakthrough', methods=['GET', 'POST'])
def rd_breakthrough():
    result = None
    ai_keys = {ai: session.get(f'{ai}_key', '') for ai in AI_CONFIGS}
    if request.method == 'POST':
        query = request.form.get('query', '').strip()
        if query:
            prompt = ("R&D breakthrough for: {query}\n"
                      "Concept, feasibility, impact. Be concise.")
            result = run_boardroom(query, prompt)
    return render_template('rd_breakthrough.html', result=result, ai_keys=ai_keys)

# === TOOL PAGES ===
@app.route('/business_tools')
def business_tools():
    return render_template('business_tools.html')

@app.route('/corporate_titan_tools')
def corporate_titan_tools():
    return render_template('corporate_titan_tools.html')

# === RUN APP ===
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
