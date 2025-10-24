from flask import Flask, request, render_template, session, redirect, url_for
from openai import OpenAI
import google.generativeai as genai
import requests
import os

app = Flask(__name__)
app.secret_key = 'boardchat2025rulez'

# Mock user database (replace with real DB in production)
USERS = {'admin': 'password123'}

AI_CONFIGS = {
    'openai': {
        'model': 'gpt-4o-mini',
        'client': lambda key: OpenAI(api_key=key),
        'generate': lambda client, prompt: client.chat.completions.create(model=AI_CONFIGS['openai']['model'], messages=[{"role": "user", "content": prompt}]).choices[0].message.content
    },
    'gemini': {
        'model': 'gemini-1.5-flash',
        'client': lambda key: (genai.configure(api_key=key), genai.GenerativeModel(AI_CONFIGS['gemini']['model']))[1],
        'generate': lambda client, prompt: client.generate_content(prompt).text
    },
    'llama': {
        'model': 'meta-llama/llama-3.1-70b-instruct:free',
        'endpoint': 'https://openrouter.ai/api/v1/chat/completions',
        'generate': lambda key, prompt: requests.post(AI_CONFIGS['llama']['endpoint'], headers={'Authorization': f'Bearer {key}'}, json={
            'model': AI_CONFIGS['llama']['model'],
            'messages': [{'role': 'user', 'content': prompt}]
        }).json()['choices'][0]['message']['content']
    },
    'claude': {
        'model': 'anthropic/claude-3.5-sonnet',
        'endpoint': 'https://openrouter.ai/api/v1/chat/completions',
        'generate': lambda key, prompt: requests.post(AI_CONFIGS['claude']['endpoint'], headers={'Authorization': f'Bearer {key}'}, json={
            'model': AI_CONFIGS['claude']['model'],
            'messages': [{'role': 'user', 'content': prompt}]
        }).json()['choices'][0]['message']['content']
    },
    'deepseek': {
        'model': 'deepseek/deepseek-chat',
        'endpoint': 'https://openrouter.ai/api/v1/chat/completions',
        'generate': lambda key, prompt: requests.post(AI_CONFIGS['deepseek']['endpoint'], headers={'Authorization': f'Bearer {key}'}, json={
            'model': AI_CONFIGS['deepseek']['model'],
            'messages': [{'role': 'user', 'content': prompt}]
        }).json()['choices'][0]['message']['content']
    },
    'grok': {
        'model': 'x-ai/grok-beta',
        'endpoint': 'https://openrouter.ai/api/v1/chat/completions',
        'generate': lambda key, prompt: requests.post(AI_CONFIGS['grok']['endpoint'], headers={'Authorization': f'Bearer {key}'}, json={
            'model': AI_CONFIGS['grok']['model'],
            'messages': [{'role': 'user', 'content': prompt}]
        }).json()['choices'][0]['message']['content']
    }
}

def run_boardroom(query, prompt="{query}"):
    active_ais = {ai: config for ai, config in AI_CONFIGS.items() if session.get(f'{ai}_key')}
    if len(active_ais) < 2:
        return "Need 2+ API keys for boardroom voting."
    responses = {}
    for ai, config in active_ais.items():
        try:
            key = session[f'{ai}_key']
            p = prompt.format(query=query)
            if 'endpoint' in config:
                resp = config['generate'](key, p)
            else:
                client = config['client'](key)
                resp = config['generate'](client, p)
            responses[ai] = resp
        except Exception as e:
            responses[ai] = f"[ERROR] {ai.upper()}: {str(e)}"
    numbered = "\n".join([f"{i+1}. {ai.upper()}: {r}" for i, (ai, r) in enumerate(responses.items())])
    vote_prompt = f"Vote for best. Reply ONLY with number:\n{numbered}"
    votes = {i+1: 0 for i in range(len(responses))}
    for ai, config in active_ais.items():
        try:
            key = session[f'{ai}_key']
            if 'endpoint' in config:
                vote = config['generate'](key, vote_prompt)
            else:
                client = config['client'](key)
                vote = config['generate'](client, vote_prompt)
            num = int(vote.strip())
            if 1 <= num <= len(votes): votes[num] += 1
        except: pass
    best = max(votes, key=votes.get)
    winner = list(responses.keys())[best-1].upper()
    result = f"**{winner} WINS ({votes[best]} votes)!**\n\n{responses[winner.lower()]}\n\n---\n\n**All Answers:**\n" + "\n\n".join([f"**{a.upper()}:**\n{r}" for a, r in responses.items()])
    session['last_chat'] = result
    return result

@app.route('/', methods=['GET', 'POST'])
def index():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    result = None
    ai_keys = {ai: session.get(f'{ai}_key', '') for ai in AI_CONFIGS}
    if request.method == 'POST':
        for ai in AI_CONFIGS:
            session[f'{ai}_key'] = request.form.get(f'{ai}_key', '').strip()
        query = request.form.get('query', '').strip()
        if query:
            result = run_boardroom(query)
    return render_template('index.html', result=result, ai_keys=ai_keys, theme=session.get('theme', 'forest'), dark_mode=session.get('dark_mode', 'off'), background=session.get('background', 'forest'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in USERS and USERS[username] == password:
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('index'))
        return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@app.route('/tools', methods=['GET'])
def tools():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    return render_template('tools.html', theme=session.get('theme', 'forest'), dark_mode=session.get('dark_mode', 'off'), background=session.get('background', 'forest'))

@app.route('/idea_eval', methods=['GET', 'POST'])
def idea_eval():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    result = None
    ai_keys = {ai: session.get(f'{ai}_key', '') for ai in AI_CONFIGS}
    if request.method == 'POST':
        query = request.form.get('query', '').strip()
        if query:
            result = run_boardroom(query, "Evaluate: {query}\nPros, cons, market fit (1-10), revenue. Be concise.")
    return render_template('idea_eval.html', result=result, ai_keys=ai_keys, theme=session.get('theme', 'forest'), dark_mode=session.get('dark_mode', 'off'), background=session.get('background', 'forest'))

@app.route('/market_research', methods=['GET', 'POST'])
def market_research():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    result = None
    ai_keys = {ai: session.get(f'{ai}_key', '') for ai in AI_CONFIGS}
    if request.method == 'POST':
        query = request.form.get('query', '').strip()
        if query:
            result = run_boardroom(query, "Market research for: {query}\nTrends, opportunities, challenges. Be concise.")
    return render_template('market_research.html', result=result, ai_keys=ai_keys, theme=session.get('theme', 'forest'), dark_mode=session.get('dark_mode', 'off'), background=session.get('background', 'forest'))

@app.route('/competitive_analysis', methods=['GET', 'POST'])
def competitive_analysis():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    result = None
    ai_keys = {ai: session.get(f'{ai}_key', '') for ai in AI_CONFIGS}
    if request.method == 'POST':
        query = request.form.get('query', '').strip()
        if query:
            result = run_boardroom(query, "Competitor analysis: {query}\nStrengths, weaknesses, recommendations. Be concise.")
    return render_template('competitive_analysis.html', result=result, ai_keys=ai_keys, theme=session.get('theme', 'forest'), dark_mode=session.get('dark_mode', 'off'), background=session.get('background', 'forest'))

@app.route('/financial_projections', methods=['GET', 'POST'])
def financial_projections():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    result = None
    ai_keys = {ai: session.get(f'{ai}_key', '') for ai in AI_CONFIGS}
    if request.method == 'POST':
        query = request.form.get('query', '').strip()
        if query:
            result = run_boardroom(query, "Financial projections for: {query}\nRevenue, costs, profit (3 years). Be concise.")
    return render_template('financial_projections.html', result=result, ai_keys=ai_keys, theme=session.get('theme', 'forest'), dark_mode=session.get('dark_mode', 'off'), background=session.get('background', 'forest'))

@app.route('/global_expansion', methods=['GET', 'POST'])
def global_expansion():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    result = None
    ai_keys = {ai: session.get(f'{ai}_key', '') for ai in AI_CONFIGS}
    if request.method == 'POST':
        query = request.form.get('query', '').strip()
        if query:
            result = run_boardroom(query, "Simulate a global expansion strategy for: {query}\nPropose 3 regions, market entry tactics, and estimated ROI (USD/year) by 2030. Be detailed.")
    return render_template('global_expansion.html', result=result, ai_keys=ai_keys, theme=session.get('theme', 'forest'), dark_mode=session.get('dark_mode', 'off'), background=session.get('background', 'forest'))

@app.route('/ai_ethics_audit', methods=['GET', 'POST'])
def ai_ethics_audit():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    result = None
    ai_keys = {ai: session.get(f'{ai}_key', '') for ai in AI_CONFIGS}
    if request.method == 'POST':
        query = request.form.get('query', '').strip()
        if query:
            result = run_boardroom(query, "Audit the AI system: {query}\nIdentify 3 ethical risks, propose mitigation strategies, and assess compliance (1-10). Be thorough.")
    return render_template('ai_ethics_audit.html', result=result, ai_keys=ai_keys, theme=session.get('theme', 'forest'), dark_mode=session.get('dark_mode', 'off'), background=session.get('background', 'forest'))

@app.route('/rd_breakthrough', methods=['GET', 'POST'])
def rd_breakthrough():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    result = None
    ai_keys = {ai: session.get(f'{ai}_key', '') for ai in AI_CONFIGS}
    if request.method == 'POST':
        query = request.form.get('query', '').strip()
        if query:
            result = run_boardroom(query, "Generate R&D breakthrough ideas for: {query}\nPropose 3 innovative projects, their potential impact, and development timeline (years). Be visionary.")
    return render_template('rd_breakthrough.html', result=result, ai_keys=ai_keys, theme=session.get('theme', 'forest'), dark_mode=session.get('dark_mode', 'off'), background=session.get('background', 'forest'))

@app.route('/business_tools', methods=['GET'])
def business_tools():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    return render_template('business_tools.html', theme=session.get('theme', 'forest'), dark_mode=session.get('dark_mode', 'off'), background=session.get('background', 'forest'))

@app.route('/corporate_titan_tools', methods=['GET'])
def corporate_titan_tools():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    return render_template('corporate_titan_tools.html', theme=session.get('theme', 'forest'), dark_mode=session.get('dark_mode', 'off'), background=session.get('background', 'forest'))

@app.route('/dashboard')
def dashboard():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    return render_template('dashboard.html', chats=12, votes=45, users=8, theme=session.get('theme', 'forest'), dark_mode=session.get('dark_mode', 'off'), background=session.get('background', 'forest'))

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    if request.method == 'POST':
        session['theme'] = request.form.get('theme', 'forest')
        session['dark_mode'] = 'on' if 'dark_mode' in request.form else 'off'
        session['review'] = request.form.get('review', '')
        session['share_link'] = 'https://boardchat-7ais.onrender.com'
        session['background'] = request.form.get('background', 'forest')
        return redirect(url_for('index'))
    current_theme = session.get('theme', 'forest')
    current_mode = session.get('dark_mode', 'off')
    current_review = session.get('review', '')
    current_background = session.get('background', 'forest')
    return render_template('settings.html', theme=current_theme, dark_mode=current_mode, review=current_review, background=current_background)

@app.route('/saved_chats')
def saved_chats():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))
    result = session.get('last_chat', 'No saved chats yet.')
    return render_template('saved_chats.html', result=result, theme=session.get('theme', 'forest'), dark_mode=session.get('dark_mode', 'off'), background=session.get('background', 'forest'))

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/static/<path:path>')
def send_static(path):
    return app.send_static_file(path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
