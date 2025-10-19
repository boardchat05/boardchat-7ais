from flask import Flask, request, render_template, session, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from openai import OpenAI
import google.generativeai as genai
import requests
import os
from oauthlib.oauth2 import WebApplicationClient
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'boardchat2025rulez')

# Google OAuth Setup
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "YOUR_GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "YOUR_GOOGLE_CLIENT_SECRET")
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

# Flask-Login Setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

AI_CONFIGS = {
    'openai': {
        'model': 'gpt-4o-mini',
        'client': lambda key: OpenAI(api_key=key),
        'generate': lambda client, prompt: client.chat.completions.create(model=AI_CONFIGS['openai']['model'], messages=[{"role": "user", "content": prompt}]).choices[0].message.content
    },
    'gemini': {
        'model': 'gemini-2.5-flash',
        'client': lambda key: (genai.configure(api_key=key), genai.GenerativeModel(AI_CONFIGS['gemini']['model']))[1],
        'generate': lambda client, prompt: client.generate_content(prompt).text
    },
    'llama': {
        'model': 'meta-llama/llama-4-maverick:free',
        'endpoint': 'https://openrouter.ai/api/v1/chat/completions',
        'generate': lambda key, prompt: requests.post(AI_CONFIGS['llama']['endpoint'], headers={'Authorization': f'Bearer {key}'}, json={
            'model': AI_CONFIGS['llama']['model'],
            'messages': [{'role': 'user', 'content': prompt}]
        }).json()['choices'][0]['message']['content']
    }
}

@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    flow = InstalledAppFlow.from_client_secrets_file('/etc/secrets/credentials.json', scopes=['openid', 'email', 'profile'])
    flow.redirect_uri = url_for('callback', _external=True)
    authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
    session['state'] = state
    return redirect(authorization_url)

@app.route('/callback')
def callback():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if 'state' not in session or session['state'] != request.args.get('state'):
        return "Invalid state parameter", 400
    flow = InstalledAppFlow.from_client_secrets_file('/etc/secrets/credentials.json', scopes=['openid', 'email', 'profile'])
    flow.redirect_uri = url_for('callback', _external=True)
    authorization_response = request.url
    flow.fetch_token(authorization_response=authorization_response)
    credentials = flow.credentials
    session['credentials'] = credentials_to_dict(credentials)
    user_info = requests.get('https://www.googleapis.com/userinfo/v2/me', headers={'Authorization': f'Bearer {credentials.token}'}).json()
    user_id = user_info['email']
    user = User(user_id)
    login_user(user)
    return redirect(url_for('index'))

def credentials_to_dict(credentials):
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('credentials', None)
    session.pop('state', None)
    return redirect(url_for('index'))

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    result = None
    ai_keys = {ai: session.get(f'{ai}_key', '') for ai in AI_CONFIGS.keys()}
    if request.method == 'POST':
        for ai in AI_CONFIGS.keys():
            session[f'{ai}_key'] = request.form.get(f'{ai}_key')
        query = request.form.get('query')
        if query:
            active_ais = {ai: config for ai, config in AI_CONFIGS.items() if session.get(f'{ai}_key')}
            if len(active_ais) < 2:
                result = "Need 2+ API keys for boardroom voting."
            else:
                responses = {}
                for ai, config in active_ais.items():
                    try:
                        key = session[f'{ai}_key']
                        if ai == 'llama':
                            resp = config['generate'](key, query)
                        else:
                            client = config['client'](key)
                            resp = config['generate'](client, query)
                        responses[ai] = resp
                    except Exception as e:
                        responses[ai] = f"Error from {ai.upper()}: {str(e)}"

                ai_list = list(responses.keys())
                numbered_responses = "\n".join([f"{i+1}. {ai.upper()}: {responses[ai]}" for i, ai in enumerate(ai_list)])
                vote_prompt = (
                    f"Boardroom vote for best answer to: '{query}'\nProposals:\n{numbered_responses}\n"
                    f"Vote for the most accurate, clear, relevant answer. Reply ONLY with the number (1-{len(ai_list)})."
                )

                votes = {i+1: 0 for i in range(len(ai_list))}
                for ai, config in active_ais.items():
                    try:
                        key = session[f'{ai}_key']
                        if ai == 'llama':
                            vote = config['generate'](key, vote_prompt)
                        else:
                            client = config['client'](key)
                            vote = config['generate'](client, vote_prompt)
                        num = int(vote.strip())
                        if 1 <= num <= len(ai_list):
                            votes[num] += 1
                    except (ValueError, Exception):
                        pass

                best_num = max(votes, key=votes.get)
                best_ai = ai_list[best_num - 1].upper()
                best_answer = responses[best_ai.lower()]
                result = (
                    f"**Boardroom Decision ({votes[best_num]} votes):** {best_ai} wins!\n\n{best_answer}\n\n"
                    f"---\n\n**All {len(ai_list)} Proposals:**\n"
                    f"{'\n\n'.join([f'**{ai.upper()}:**\n{resp}' for ai, resp in responses.items()])}"
                )

    return render_template('index.html', result=result, ai_keys=ai_keys, email=current_user.id if current_user.is_authenticated else None)

@app.route('/tools', methods=['GET'])
@login_required
def tools():
    return render_template('tools.html')

@app.route('/idea_eval', methods=['GET', 'POST'])
@login_required
def idea_eval():
    result = None
    ai_keys = {ai: session.get(f'{ai}_key', '') for ai in AI_CONFIGS.keys()}
    if request.method == 'POST':
        query = request.form.get('query')
        if query:
            active_ais = {ai: config for ai, config in AI_CONFIGS.items() if session.get(f'{ai}_key')}
            if len(active_ais) < 2:
                result = "Need 2+ API keys for idea evaluation."
            else:
                prompt = f"Evaluate the business idea: {query}. Provide pros, cons, market fit (1-10), and potential revenue (USD/year). Be concise."
                responses = {}
                for ai, config in active_ais.items():
                    try:
                        key = session[f'{ai}_key']
                        if ai == 'llama':
                            resp = config['generate'](key, prompt)
                        else:
                            client = config['client'](key)
                            resp = config['generate'](client, prompt)
                        responses[ai] = resp
                    except Exception as e:
                        responses[ai] = f"Error from {ai.upper()}: {str(e)}"

                ai_list = list(responses.keys())
                numbered_responses = "\n".join([f"{i+1}. {ai.upper()}: {responses[ai]}" for i, ai in enumerate(ai_list)])
                vote_prompt = (
                    f"Vote for the best business idea evaluation for: '{query}'\nEvaluations:\n{numbered_responses}\n"
                    f"Vote for the most viable idea based on market fit and revenue potential. Reply ONLY with the number (1-{len(ai_list)})."
                )

                votes = {i+1: 0 for i in range(len(ai_list))}
                for ai, config in active_ais.items():
                    try:
                        key = session[f'{ai}_key']
                        if ai == 'llama':
                            vote = config['generate'](key, vote_prompt)
                        else:
                            client = config['client'](key)
                            vote = config['generate'](client, vote_prompt)
                        num = int(vote.strip())
                        if 1 <= num <= len(ai_list):
                            votes[num] += 1
                    except (ValueError, Exception):
                        pass

                best_num = max(votes, key=votes.get)
                best_ai = ai_list[best_num - 1].upper()
                best_answer = responses[best_ai.lower()]
                result = (
                    f"**Best Business Idea ({votes[best_num]} votes):** {best_ai} wins!\n\n{best_answer}\n\n"
                    f"---\n\n**All {len(ai_list)} Evaluations:**\n"
                    f"{'\n\n'.join([f'**{ai.upper()}:**\n{resp}' for ai, resp in responses.items()])}"
                )
    return render_template('idea_eval.html', result=result, ai_keys=ai_keys)

@app.route('/market_research', methods=['GET', 'POST'])
@login_required
def market_research():
    result = None
    ai_keys = {ai: session.get(f'{ai}_key', '') for ai in AI_CONFIGS.keys()}
    if request.method == 'POST':
        query = request.form.get('query')
        if query:
            active_ais = {ai: config for ai, config in AI_CONFIGS.items() if session.get(f'{ai}_key')}
            if len(active_ais) < 2:
                result = "Need 2+ API keys for market research."
            else:
                prompt = f"Summarize market research for: {query}. Provide key trends, opportunities, and challenges. Be concise."
                responses = {}
                for ai, config in active_ais.items():
                    try:
                        key = session[f'{ai}_key']
                        if ai == 'llama':
                            resp = config['generate'](key, prompt)
                        else:
                            client = config['client'](key)
                            resp = config['generate'](client, prompt)
                        responses[ai] = resp
                    except Exception as e:
                        responses[ai] = f"Error from {ai.upper()}: {str(e)}"

                ai_list = list(responses.keys())
                numbered_responses = "\n".join([f"{i+1}. {ai.upper()}: {responses[ai]}" for i, ai in enumerate(ai_list)])
                vote_prompt = (
                    f"Vote for the best market research summary for: '{query}'\nSummaries:\n{numbered_responses}\n"
                    f"Vote for the most insightful and accurate summary. Reply ONLY with the number (1-{len(ai_list)})."
                )

                votes = {i+1: 0 for i in range(len(ai_list))}
                for ai, config in active_ais.items():
                    try:
                        key = session[f'{ai}_key']
                        if ai == 'llama':
                            vote = config['generate'](key, vote_prompt)
                        else:
                            client = config['client'](key)
                            vote = config['generate'](client, vote_prompt)
                        num = int(vote.strip())
                        if 1 <= num <= len(ai_list):
                            votes[num] += 1
                    except (ValueError, Exception):
                        pass

                best_num = max(votes, key=votes.get)
                best_ai = ai_list[best_num - 1].upper()
                best_answer = responses[best_ai.lower()]
                result = (
                    f"**Best Market Research ({votes[best_num]} votes):** {best_ai} wins!\n\n{best_answer}\n\n"
                    f"---\n\n**All {len(ai_list)} Summaries:**\n"
                    f"{'\n\n'.join([f'**{ai.upper()}:**\n{resp}' for ai, resp in responses.items()])}"
                )
    return render_template('market_research.html', result=result, ai_keys=ai_keys)

@app.route('/competitive_analysis', methods=['GET', 'POST'])
@login_required
def competitive_analysis():
    result = None
    ai_keys = {ai: session.get(f'{ai}_key', '') for ai in AI_CONFIGS.keys()}
    if request.method == 'POST':
        query = request.form.get('query')
        if query:
            active_ais = {ai: config for ai, config in AI_CONFIGS.items() if session.get(f'{ai}_key')}
            if len(active_ais) < 2:
                result = "Need 2+ API keys for competitive analysis."
            else:
                prompt = f"Analyze competitors for: {query}. Provide strengths, weaknesses, and actionable recommendations. Be concise."
                responses = {}
                for ai, config in active_ais.items():
                    try:
                        key = session[f'{ai}_key']
                        if ai == 'llama':
                            resp = config['generate'](key, prompt)
                        else:
                            client = config['client'](key)
                            resp = config['generate'](client, prompt)
                        responses[ai] = resp
                    except Exception as e:
                        responses[ai] = f"Error from {ai.upper()}: {str(e)}"

                ai_list = list(responses.keys())
                numbered_responses = "\n".join([f"{i+1}. {ai.upper()}: {responses[ai]}" for i, ai in enumerate(ai_list)])
                vote_prompt = (
                    f"Vote for the best competitive analysis for: '{query}'\nAnalyses:\n{numbered_responses}\n"
                    f"Vote for the most actionable and insightful analysis. Reply ONLY with the number (1-{len(ai_list)})."
                )

                votes = {i+1: 0 for i in range(len(ai_list))}
                for ai, config in active_ais.items():
                    try:
                        key = session[f'{ai}_key']
                        if ai == 'llama':
                            vote = config['generate'](key, vote_prompt)
                        else:
                            client = config['client'](key)
                            vote = config['generate'](client, vote_prompt)
                        num = int(vote.strip())
                        if 1 <= num <= len(ai_list):
                            votes[num] += 1
                    except (ValueError, Exception):
                        pass

                best_num = max(votes, key=votes.get)
                best_ai = ai_list[best_num - 1].upper()
                best_answer = responses[best_ai.lower()]
                result = (
                    f"**Best Competitive Analysis ({votes[best_num]} votes):** {best_ai} wins!\n\n{best_answer}\n\n"
                    f"---\n\n**All {len(ai_list)} Analyses:**\n"
                    f"{'\n\n'.join([f'**{ai.upper()}:**\n{resp}' for ai, resp in responses.items()])}"
                )
    return render_template('competitive_analysis.html', result=result, ai_keys=ai_keys)

@app.route('/financial_projections', methods=['GET', 'POST'])
@login_required
def financial_projections():
    result = None
    ai_keys = {ai: session.get(f'{ai}_key', '') for ai in AI_CONFIGS.keys()}
    if request.method == 'POST':
        query = request.form.get('query')
        if query:
            active_ais = {ai: config for ai, config in AI_CONFIGS.items() if session.get(f'{ai}_key')}
            if len(active_ais) < 2:
                result = "Need 2+ API keys for financial projections."
            else:
                prompt = f"Generate financial projections for: {query}. Provide estimated revenue, costs, and net profit (USD/year) for the next 3 years. Be concise."
                responses = {}
                for ai, config in active_ais.items():
                    try:
                        key = session[f'{ai}_key']
                        if ai == 'llama':
                            resp = config['generate'](key, prompt)
                        else:
                            client = config['client'](key)
                            resp = config['generate'](client, prompt)
                        responses[ai] = resp
                    except Exception as e:
                        responses[ai] = f"Error from {ai.upper()}: {str(e)}"

                ai_list = list(responses.keys())
                numbered_responses = "\n".join([f"{i+1}. {ai.upper()}: {responses[ai]}" for i, ai in enumerate(ai_list)])
                vote_prompt = (
                    f"Vote for the best financial projection for: '{query}'\nProjections:\n{numbered_responses}\n"
                    f"Vote for the most realistic and detailed projection. Reply ONLY with the number (1-{len(ai_list)})."
                )

                votes = {i+1: 0 for i in range(len(ai_list))}
                for ai, config in active_ais.items():
                    try:
                        key = session[f'{ai}_key']
                        if ai == 'llama':
                            vote = config['generate'](key, vote_prompt)
                        else:
                            client = config['client'](key)
                            vote = config['generate'](client, vote_prompt)
                        num = int(vote.strip())
                        if 1 <= num <= len(ai_list):
                            votes[num] += 1
                    except (ValueError, Exception):
                        pass

                best_num = max(votes, key=votes.get)
                best_ai = ai_list[best_num - 1].upper()
                best_answer = responses[best_ai.lower()]
                result = (
                    f"**Best Financial Projection ({votes[best_num]} votes):** {best_ai} wins!\n\n{best_answer}\n\n"
                    f"---\n\n**All {len(ai_list)} Projections:**\n"
                    f"{'\n\n'.join([f'**{ai.upper()}:**\n{resp}' for ai, resp in responses.items()])}"
                )
    return render_template('financial_projections.html', result=result, ai_keys=ai_keys)

@app.route('/global_expansion', methods=['GET', 'POST'])
@login_required
def global_expansion():
    result = None
    ai_keys = {ai: session.get(f'{ai}_key', '') for ai in AI_CONFIGS.keys()}
    if request.method == 'POST':
        query = request.form.get('query')
        if query:
            active_ais = {ai: config for ai, config in AI_CONFIGS.items() if session.get(f'{ai}_key')}
            if len(active_ais) < 2:
                result = "Need 2+ API keys for global expansion simulation."
            else:
                prompt = f"Simulate a global expansion strategy for: {query}. Propose 3 regions, market entry tactics, and estimated ROI (USD/year) by 2030. Be detailed."
                responses = {}
                for ai, config in active_ais.items():
                    try:
                        key = session[f'{ai}_key']
                        if ai == 'llama':
                            resp = config['generate'](key, prompt)
                        else:
                            client = config['client'](key)
                            resp = config['generate'](client, prompt)
                        responses[ai] = resp
                    except Exception as e:
                        responses[ai] = f"Error from {ai.upper()}: {str(e)}"

                ai_list = list(responses.keys())
                numbered_responses = "\n".join([f"{i+1}. {ai.upper()}: {responses[ai]}" for i, ai in enumerate(ai_list)])
                vote_prompt = (
                    f"Vote for the best global expansion strategy for: '{query}'\nStrategies:\n{numbered_responses}\n"
                    f"Vote for the most feasible and high-ROI strategy. Reply ONLY with the number (1-{len(ai_list)})."
                )

                votes = {i+1: 0 for i in range(len(ai_list))}
                for ai, config in active_ais.items():
                    try:
                        key = session[f'{ai}_key']
                        if ai == 'llama':
                            vote = config['generate'](key, vote_prompt)
                        else:
                            client = config['client'](key)
                            vote = config['generate'](client, vote_prompt)
                        num = int(vote.strip())
                        if 1 <= num <= len(ai_list):
                            votes[num] += 1
                    except (ValueError, Exception):
                        pass

                best_num = max(votes, key=votes.get)
                best_ai = ai_list[best_num - 1].upper()
                best_answer = responses[best_ai.lower()]
                result = (
                    f"**Best Global Expansion Strategy ({votes[best_num]} votes):** {best_ai} wins!\n\n{best_answer}\n\n"
                    f"---\n\n**All {len(ai_list)} Strategies:**\n"
                    f"{'\n\n'.join([f'**{ai.upper()}:**\n{resp}' for ai, resp in responses.items()])}"
                )
    return render_template('global_expansion.html', result=result, ai_keys=ai_keys)

@app.route('/ai_ethics_audit', methods=['GET', 'POST'])
@login_required
def ai_ethics_audit():
    result = None
    ai_keys = {ai: session.get(f'{ai}_key', '') for ai in AI_CONFIGS.keys()}
    if request.method == 'POST':
        query = request.form.get('query')
        if query:
            active_ais = {ai: config for ai, config in AI_CONFIGS.items() if session.get(f'{ai}_key')}
            if len(active_ais) < 2:
                result = "Need 2+ API keys for AI ethics audit."
            else:
                prompt = f"Audit the AI system: {query}. Identify 3 ethical risks, propose mitigation strategies, and assess compliance (1-10). Be thorough."
                responses = {}
                for ai, config in active_ais.items():
                    try:
                        key = session[f'{ai}_key']
                        if ai == 'llama':
                            resp = config['generate'](key, prompt)
                        else:
                            client = config['client'](key)
                            resp = config['generate'](client, prompt)
                        responses[ai] = resp
                    except Exception as e:
                        responses[ai] = f"Error from {ai.upper()}: {str(e)}"

                ai_list = list(responses.keys())
                numbered_responses = "\n".join([f"{i+1}. {ai.upper()}: {responses[ai]}" for i, ai in enumerate(ai_list)])
                vote_prompt = (
                    f"Vote for the best AI ethics audit for: '{query}'\nAudits:\n{numbered_responses}\n"
                    f"Vote for the most comprehensive and actionable audit. Reply ONLY with the number (1-{len(ai_list)})."
                )

                votes = {i+1: 0 for i in range(len(ai_list))}
                for ai, config in active_ais.items():
                    try:
                        key = session[f'{ai}_key']
                        if ai == 'llama':
                            vote = config['generate'](key, vote_prompt)
                        else:
                            client = config['client'](key)
                            vote = config['generate'](client, vote_prompt)
                        num = int(vote.strip())
                        if 1 <= num <= len(ai_list):
                            votes[num] += 1
                    except (ValueError, Exception):
                        pass

                best_num = max(votes, key=votes.get)
                best_ai = ai_list[best_num - 1].upper()
                best_answer = responses[best_ai.lower()]
                result = (
                    f"**Best AI Ethics Audit ({votes[best_num]} votes):** {best_ai} wins!\n\n{best_answer}\n\n"
                    f"---\n\n**All {len(ai_list)} Audits:**\n"
                    f"{'\n\n'.join([f'**{ai.upper()}:**\n{resp}' for ai, resp in responses.items()])}"
                )
    return render_template('ai_ethics_audit.html', result=result, ai_keys=ai_keys)

@app.route('/rd_breakthrough', methods=['GET', 'POST'])
@login_required
def rd_breakthrough():
    result = None
    ai_keys = {ai: session.get(f'{ai}_key', '') for ai in AI_CONFIGS.keys()}
    if request.method == 'POST':
        query = request.form.get('query')
        if query:
            active_ais = {ai: config for ai, config in AI_CONFIGS.items() if session.get(f'{ai}_key')}
            if len(active_ais) < 2:
                result = "Need 2+ API keys for R&D breakthrough generation."
            else:
                prompt = f"Generate R&D breakthrough ideas for: {query}. Propose 3 innovative projects, their potential impact, and development timeline (years). Be visionary."
                responses = {}
                for ai, config in active_ais.items():
                    try:
                        key = session[f'{ai}_key']
                        if ai == 'llama':
                            resp = config['generate'](key, prompt)
                        else:
                            client = config['client'](key)
                            resp = config['generate'](client, prompt)
                        responses[ai] = resp
                    except Exception as e:
                        responses[ai] = f"Error from {ai.upper()}: {str(e)}"

                ai_list = list(responses.keys())
                numbered_responses = "\n".join([f"{i+1}. {ai.upper()}: {responses[ai]}" for i, ai in enumerate(ai_list)])
                vote_prompt = (
                    f"Vote for the best R&D breakthrough idea for: '{query}'\nIdeas:\n{numbered_responses}\n"
                    f"Vote for the most innovative and impactful idea. Reply ONLY with the number (1-{len(ai_list)})."
                )

                votes = {i+1: 0 for i in range(len(ai_list))}
                for ai, config in active_ais.items():
                    try:
                        key = session[f'{ai}_key']
                        if ai == 'llama':
                            vote = config['generate'](key, vote_prompt)
                        else:
                            client = config['client'](key)
                            vote = config['generate'](client, vote_prompt)
                        num = int(vote.strip())
                        if 1 <= num <= len(ai_list):
                            votes[num] += 1
                    except (ValueError, Exception):
                        pass

                best_num = max(votes, key=votes.get)
                best_ai = ai_list[best_num - 1].upper()
                best_answer = responses[best_ai.lower()]
                result = (
                    f"**Best R&D Breakthrough ({votes[best_num]} votes):** {best_ai} wins!\n\n{best_answer}\n\n"
                    f"---\n\n**All {len(ai_list)} Ideas:**\n"
                    f"{'\n\n'.join([f'**{ai.upper()}:**\n{resp}' for ai, resp in responses.items()])}"
                )
    return render_template('rd_breakthrough.html', result=result, ai_keys=ai_keys)

if __name__ == '__main__':
    app.run(debug=True)
