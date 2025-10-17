from flask import Flask, request, render_template, session
from openai import OpenAI
import google.generativeai as genai
import anthropic
from groq import Groq
import requests

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
    },
    'deepseek': {
        'model': 'deepseek-chat',
        'client': lambda key: OpenAI(api_key=key, base_url="https://api.deepseek.com"),
        'generate': lambda client, prompt: client.chat.completions.create(model=AI_CONFIGS['deepseek']['model'], messages=[{"role": "user", "content": prompt}]).choices[0].message.content
    },
    'claude': {
        'model': 'claude-3.7-sonnet-20250219',
        'client': lambda key: anthropic.Anthropic(api_key=key),
        'generate': lambda client, prompt: client.messages.create(model=AI_CONFIGS['claude']['model'], max_tokens=1000, messages=[{"role": "user", "content": prompt}]).content[0].text
    },
    'grok': {
        'model': 'mixtral-8x7b-32768',  # Updated to a valid Groq model
        'client': lambda key: Groq(api_key=key),
        'generate': lambda client, prompt: client.chat.completions.create(model=AI_CONFIGS['grok']['model'], messages=[{"role": "user", "content": prompt}]).choices[0].message.content
    },
    'llama': {
        'model': 'meta-llama/llama-4-70b-instruct',
        'endpoint': 'https://api.groq.com/openai/v1/chat/completions',
        'generate': lambda key, prompt: requests.post(AI_CONFIGS['llama']['endpoint'], headers={'Authorization': f'Bearer {key}'}, json={
            'model': AI_CONFIGS['llama']['model'], 'messages': [{'role': 'user', 'content': prompt}]
        }).json()['choices'][0]['message']['content']
    },
    'mistral': {
        'model': 'mistral-large-latest',
        'endpoint': 'https://api.mistral.ai/v1/chat/completions',
        'generate': lambda key, prompt: requests.post(AI_CONFIGS['mistral']['endpoint'], headers={'Authorization': f'Bearer {key}'}, json={
            'model': AI_CONFIGS['mistral']['model'], 'messages': [{'role': 'user', 'content': prompt}]
        }).json()['choices'][0]['message']['content']
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
                numbered_responses = "\n".join([f"{i+1}. {ai.upper()}: {responses[ai]}" for i, ai in enumerate(ai_list)])
                vote_prompt = (
                    f"Boardroom vote for best answer to: '{query}'\nProposals:\n{numbered_responses}\n"
                    f"Vote for the most accurate, clear, relevant answer. Reply ONLY with the number (1-{len(ai_list)})."
                )

                votes = {i+1: 0 for i in range(len(ai_list))}
                for ai, config in active_ais.items():
                    try:
                        key = session[f'{ai}_key']
                        if 'endpoint' in config:
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

    return render_template('index.html', result=result, ai_keys=ai_keys)

if __name__ == '__main__':
    app.run(debug=True)
