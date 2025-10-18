from flask import Flask, request, render_template, session
from openai import OpenAI
import google.generativeai as genai

app = Flask(__name__)
app.secret_key = 'boardchat2025rulez'

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
    }
}

@app.route('/', methods=['GET', 'POST'])
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
                        if 'endpoint' in config:
                            resp = config['generate'](key, query)
                        else:
                            client = config['client'](key)
                            resp = config['generate'](client, query)
                        responses[ai] = resp
                    except Exception as e:
                        responses[ai] = f"Error from {ai.upper()}: {str(e)}"

                ai_list = list(responses.keys())
