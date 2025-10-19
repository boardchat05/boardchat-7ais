from flask import Flask, request, render_template, session
from openai import OpenAI
import google.generativeai as genai
from groq import Groq

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
    'groq': {
        'model': 'llama3-70b-8192',
        'client': lambda key: Groq(api_key=key),
        'generate': lambda client, prompt: client.chat.completions.create(model=AI_CONFIGS['groq']['model'], messages=[{"role": "user", "content": prompt}]).choices[0].message.content
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
                        client = config['client'](key) if 'client' in config else None
                        resp = config['generate'](client, query) if client else config['generate'](key, query)
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
                        client = config['client'](key) if 'client' in config else None
                        vote = config['generate'](client, vote_prompt) if client else config['generate'](key, vote_prompt)
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

@app.route('/tools', methods=['GET'])
def tools():
    return render_template('tools.html')

@app.route('/idea_eval', methods=['GET', 'POST'])
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
                        client = config['client'](key) if 'client' in config else None
                        resp = config['generate'](client, prompt) if client else config['generate'](key, prompt)
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
                        client = config['client'](key) if 'client' in config else None
                        vote = config['generate'](client, vote_prompt) if client else config['generate'](key, vote_prompt)
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
                        client = config['client'](key) if 'client' in config else None
                        resp = config['generate'](client, prompt) if client else config['generate'](key, prompt)
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
                        client = config['client'](key) if 'client' in config else None
                        vote = config['generate'](client, vote_prompt) if client else config['generate'](key, vote_prompt)
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
                        client = config['client'](key) if 'client' in config else None
                        resp = config['generate'](client, prompt) if client else config['generate'](key, prompt)
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
                        client = config['client'](key) if 'client' in config else None
                        vote = config['generate'](client, vote_prompt) if client else config['generate'](key, vote_prompt)
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
                        client = config['client'](key) if 'client' in config else None
                        resp = config['generate'](client, prompt) if client else config['generate'](key, prompt)
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
                        client = config['client'](key) if 'client' in config else None
                        vote = config['generate'](client, vote_prompt) if client else config['generate'](key, vote_prompt)
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

if __name__ == '__main__':
    app.run(debug=True)
