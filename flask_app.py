from flask import Flask, request, render_template, session, redirect, url_for
from openai import OpenAI
import google.generativeai as genai
import requests
import os

app = Flask(__name__)
app.secret_key = 'boardchat2025rulez'

# === 6 AI MODELS ===
AI_CONFIGS = {
    'openai': {'model': 'gpt-4o-mini', 'client': lambda k: OpenAI(api_key=k), 'gen': lambda c,p: c.chat.completions.create(model='gpt-4o-mini', messages=[{'role':'user','content':p}]).choices[0].message.content},
    'gemini': {'model': 'gemini-1.5-flash', 'client': lambda k: (genai.configure(api_key=k), genai.GenerativeModel('gemini-1.5-flash'))[1], 'gen': lambda c,p: c.generate_content(p).text},
    'llama': {'model': 'meta-llama/llama-3.1-70b-instruct:free', 'endpoint': 'https://openrouter.ai/api/v1/chat/completions', 'gen': lambda k,p: requests.post('https://openrouter.ai/api/v1/chat/completions', headers={'Authorization': f'Bearer {k}'}, json={'model': 'meta-llama/llama-3.1-70b-instruct:free', 'messages': [{'role':'user','content':p}]}).json()['choices'][0]['message']['content']},
    'claude': {'model': 'anthropic/claude-3.5-sonnet', 'endpoint': 'https://openrouter.ai/api/v1/chat/completions', 'gen': lambda k,p: requests.post('https://openrouter.ai/api/v1/chat/completions', headers={'Authorization': f'Bearer {k}'}, json={'model': 'anthropic/claude-3.5-sonnet', 'messages': [{'role':'user','content':p}]}).json()['choices'][0]['message']['content']},
    'deepseek': {'model': 'deepseek/deepseek-chat', 'endpoint': 'https://openrouter.ai/api/v1/chat/completions', 'gen': lambda k,p: requests.post('https://openrouter.ai/api/v1/chat/completions', headers={'Authorization': f'Bearer {k}'}, json={'model': 'deepseek/deepseek-chat', 'messages': [{'role':'user','content':p}]}).json()['choices'][0]['message']['content']},
    'grok': {'model': 'x-ai/grok-beta', 'endpoint': 'https://openrouter.ai/api/v1/chat/completions', 'gen': lambda k,p: requests.post('https://openrouter.ai/api/v1/chat/completions', headers={'Authorization': f'Bearer {k}'}, json={'model': 'x-ai/grok-beta', 'messages': [{'role':'user','content':p}]}).json()['choices'][0]['message']['content']}
}

def run_boardroom(query, prompt="{query}"):
    active = {a: c for a,c in AI_CONFIGS.items() if session.get(f'{a}_key')}
    if len(active) < 2: return "Need 2+ API keys."
    responses = {}
    for a, c in active.items():
        try:
            key = session[f'{a}_key']
            p = prompt.format(query=query)
            responses[a] = c['gen'](c['client'](key) if 'client' in c else key, p)
        except Exception as e:
            responses[a] = f"[ERROR] {a.upper()}: {str(e)}"
    numbered = "\n".join([f"{i+1}. {a.upper()}: {r}" for i,(a,r) in enumerate(responses.items())])
    vote_prompt = f"Vote for best. Reply ONLY with number:\n{numbered}"
    votes = {i+1:0 for i in range(len(responses))}
    for a, c in active.items():
        try:
            key = session[f'{a}_key']
            vote = c['gen'](c['client'](key) if 'client' in c else key, vote_prompt)
            num = int(vote.strip())
            if 1 <= num <= len(votes): votes[num] += 1
        except: pass
    best = max(votes, key=votes.get)
    winner = list(responses.keys())[best-1].upper()
    result = f"**{winner} WINS ({votes[best]} votes)!**\n\n{responses[winner.lower()]}\n\n---\n\n**All Answers:**\n" + "\n\n".join([f"**{a.upper()}:**\n{r}" for a,r in responses.items()])
    session['last_chat'] = result  # SAVE CHAT
    return result

@app.route('/', methods=['GET','POST'])
def index():
    result = None
    keys = {a: session.get(f'{a}_key','') for a in AI_CONFIGS}
    if request.method == 'POST':
        for a in AI_CONFIGS: session[f'{a}_key'] = request.form.get(f'{a}_key','').strip()
        query = request.form.get('query','').strip()
        if query: result = run_boardroom(query)
    return render_template('index.html', result=result, ai_keys=keys, theme=session.get('theme', 'forest'), dark_mode=session.get('dark_mode', 'off'), background=session.get('background', 'forest'))

@app.route('/idea_eval', methods=['GET','POST'])
def idea_eval():
    result = None
    keys = {a: session.get(f'{a}_key','') for a in AI_CONFIGS}
    if request.method == 'POST':
        query = request.form.get('query','').strip()
        if query: result = run_boardroom(query, "Evaluate: {query}\nPros, cons, market fit (1-10), revenue. Be concise.")
    return render_template('idea_eval.html', result=result, ai_keys=keys, theme=session.get('theme', 'forest'), dark_mode=session.get('dark_mode', 'off'), background=session.get('background', 'forest'))

@app.route('/market_research', methods=['GET','POST'])
def market_research():
    result = None
    keys = {a: session.get(f'{a}_key','') for a in AI_CONFIGS}
    if request.method == 'POST':
        query = request.form.get('query','').strip()
        if query: result = run_boardroom(query, "Market research for: {query}\nTrends, opportunities, challenges. Be concise.")
    return render_template('market_research.html', result=result, ai_keys=keys, theme=session.get('theme', 'forest'), dark_mode=session.get('dark_mode', 'off'), background=session.get('background', 'forest'))

@app.route('/competitive_analysis', methods=['GET','POST'])
def competitive_analysis():
    result = None
    keys = {a: session.get(f'{a}_key','') for a in AI_CONFIGS}
    if request.method == 'POST':
        query = request.form.get('query','').strip()
        if query: result = run_boardroom(query, "Competitor analysis: {query}\nStrengths, weaknesses, recommendations. Be concise.")
    return render_template('competitive_analysis.html', result=result, ai_keys=keys, theme=session.get('theme', 'forest'), dark_mode=session.get('dark_mode', 'off'), background=session.get('background', 'forest'))

@app.route('/financial_projections', methods=['GET','POST'])
def financial_projections():
    result = None
    keys = {a: session.get(f'{a}_key','') for a in AI_CONFIGS}
    if request.method == 'POST':
        query = request.form.get('query','').strip()
        if query: result = run_boardroom(query, "Financial projections for: {query}\nRevenue, costs, profit (3 years). Be concise.")
    return render_template('financial_projections.html', result=result, ai_keys=keys, theme=session.get('theme', 'forest'), dark_mode=session.get('dark_mode', 'off'), background=session.get('background', 'forest'))

@app.route('/settings', methods=['GET','POST'])
def settings():
    if request.method == 'POST':
        # Save theme, mode, review, and background
        session['theme'] = request.form.get('theme', 'forest')
        session['dark_mode'] = 'on' if 'dark_mode' in request.form else 'off'
        session['review'] = request.form.get('review', '')
        session['share_link'] = 'https://boardchat-7ais.onrender.com'
        session['background'] = request.form.get('background', 'forest')
        return redirect(url_for('index'))
    
    # Load current settings
    current_theme = session.get('theme', 'forest')
    current_mode = session.get('dark_mode', 'off')
    current_review = session.get('review', '')
    current_background = session.get('background', 'forest')
    
    return render_template('settings.html', theme=current_theme, dark_mode=current_mode, review=current_review, background=current_background)

@app.route('/saved_chats')
def saved_chats():
    result = session.get('last_chat', 'No saved chats yet.')
    return render_template('saved_chats.html', result=result, theme=session.get('theme', 'forest'), dark_mode=session.get('dark_mode', 'off'), background=session.get('background', 'forest'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/tools')
def tools():
    return render_template('tools.html', theme=session.get('theme', 'forest'), dark_mode=session.get('dark_mode', 'off'), background=session.get('background', 'forest'))

# Serve static files explicitly (fallback for Render)
@app.route('/static/<path:path>')
def send_static(path):
    return app.send_static_file(path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
