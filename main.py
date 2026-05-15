# imports
# If these fail, please check you're running from an 'activated' environment with (llms) in the command prompt

import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context

from bs4 import BeautifulSoup
import requests


# Standard headers to fetch a website
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
}


def fetch_website_contents(url):
    """
    Return the title and contents of the website at the given url;
    truncate to 2,000 characters as a sensible limit
    """
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")
    title = soup.title.string if soup.title else "No title found"
    if soup.body:
        for irrelevant in soup.body(["script", "style", "img", "input"]):
            irrelevant.decompose()
        text = soup.body.get_text(separator="\n", strip=True)
    else:
        text = ""
    return (title + "\n\n" + text)[:2_000]


def fetch_website_links(url):
    """
    Return the links on the webiste at the given url
    I realize this is inefficient as we're parsing twice! This is to keep the code in the lab simple.
    Feel free to use a class and optimize it!
    """
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")
    links = [link.get("href") for link in soup.find_all("a")]
    return [link for link in links if link]


# Initialize and constants

load_dotenv(override=True)
api_key = os.getenv('OPENAI_API_KEY')

if api_key and api_key.startswith('sk-proj-') and len(api_key)>10:
    print("API key looks good so far")
else:
    print("There might be a problem with your API key? Please visit the troubleshooting notebook!")
    
MODEL = 'gpt-5-nano'
openai = OpenAI()

# links = fetch_website_links("https://edwarddonner.com")
# links

from datetime import date

usage_tracker = {}

def check_rate_limit(ip_address):
    today = date.today()

    if ip_address not in usage_tracker:
        usage_tracker[ip_address] = {"count": 0, "date": today}

    if usage_tracker[ip_address]["date"] != today:
        usage_tracker[ip_address] = {"count": 0, "date": today}

    if usage_tracker[ip_address]["count"] >= 10:
        return False  # blocked

    usage_tracker[ip_address]["count"] += 1
    return True  # allowed


link_system_prompt = """
You are provided with a list of links found on a webpage.
You are able to decide which of the links would be most relevant to include in a brochure about the company,
such as links to an About page, or a Company page, or Careers/Jobs pages.
You should respond in JSON as in this example:

{
    "links": [
        {"type": "about page", "url": "https://full.url/goes/here/about"},
        {"type": "careers page", "url": "https://another.full.url/careers"}
    ]
}
"""

def get_links_user_prompt(url):
    user_prompt = f"""
Here is the list of links on the website {url} -
Please decide which of these are relevant web links for a brochure about the company, 
respond with the full https URL in JSON format.
Do not include Terms of Service, Privacy, email links.

Links (some might be relative links):

"""
    links = fetch_website_links(url)
    user_prompt += "\n".join(links)
    return user_prompt


# print(get_links_user_prompt("https://edwarddonner.com"))

def select_relevant_links(url):
    response = openai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": link_system_prompt},
            {"role": "user", "content": get_links_user_prompt(url)}
        ],
        response_format={"type": "json_object"}
    )
    result = response.choices[0].message.content
    links = json.loads(result)
    return links
    

# select_relevant_links("https://edwarddonner.com")

def fetch_page_and_all_relevant_links(url):
    contents = fetch_website_contents(url)
    relevant_links = select_relevant_links(url)
    result = f"## Landing Page:\n\n{contents}\n## Relevant Links:\n"
    for link in relevant_links['links']:
        result += f"\n\n### Link: {link['type']}\n"
        result += fetch_website_contents(link["url"])
    return result


brochure_system_prompt = """
You are an assistant that analyzes the contents of several relevant pages from a company website
and creates a short brochure about the company for prospective customers, investors and recruits.
Respond in markdown without code blocks.
Include details of company culture, customers and careers/jobs if you have the information.
"""

# Or uncomment the lines below for a more humorous brochure - this demonstrates how easy it is to incorporate 'tone':

# brochure_system_prompt = """
# You are an assistant that analyzes the contents of several relevant pages from a company website
# and creates a short, humorous, entertaining, witty brochure about the company for prospective customers, investors and recruits.
# Respond in markdown without code blocks.
# Include details of company culture, customers and careers/jobs if you have the information.
# """

# def get_brochure_user_prompt(company_name, url):
   # user_prompt = f"""
# You are looking at a company called: {company_name}
# Here are the contents of its landing page and other relevant pages;
# use this information to build a short brochure of the company in markdown without code blocks.\n\n
# """
#     user_prompt += fetch_page_and_all_relevant_links(url)
#     user_prompt = user_prompt[:5_000] # Truncate if more than 5,000 characters
#     return user_prompt


def get_brochure_user_prompt(company_name, url, audience):
    audience_instructions = {
        'investors': 'Focus on financial performance, growth potential, market position, and leadership team.',
        'recruits': 'Focus on company culture, career opportunities, benefits, and team environment.',
        'clients': 'Focus on products and services, customer success stories, and company values.'
    }
    instruction = audience_instructions.get(audience, '')
    user_prompt = f"""
You are looking at a company called: {company_name}
This brochure is intended for: {audience}.
{instruction}
Here are the contents of its landing page and other relevant pages;
use this information to build a short brochure in markdown without code blocks.\n\n
"""
    user_prompt += fetch_page_and_all_relevant_links(url)
    user_prompt = user_prompt[:5_000]
    return user_prompt


app = Flask(__name__)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/generate', methods=['POST'])
def generate():
    data = request.get_json()
    ip = request.remote_addr

    if not check_rate_limit(ip):
        return jsonify({'error': 'You have reached the daily limit of 3 brochures. Please come back tomorrow.'}), 429

    company_name = data.get('company_name', '').strip()
    url = data.get('url', '').strip()
    audience = data.get('audience', 'clients').strip()

    if not company_name or not url:
        return jsonify({'error': 'Company name and URL are required.'}), 400


    def stream_brochure():
        try:
            yield "data: [STATUS] Scanning website...\n\n"
            user_prompt = get_brochure_user_prompt(company_name, url, audience)
            yield "data: [STATUS] Analyzing content...\n\n"
            stream = openai.chat.completions.create(
                model='gpt-4.1-mini',
                max_completion_tokens=800,
                messages=[
                    {'role': 'system', 'content': brochure_system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ],
                stream=True
            )
            yield "data: [STATUS] Generating brochure...\n\n"
            for chunk in stream:
                text = chunk.choices[0].delta.content or ''
                if text:
                    escaped = text.replace('\n', '\\n')
                    yield f"data: {escaped}\n\n"
        except Exception as e:
            yield f"data: [ERROR] Something went wrong. Please try again.\n\n"

    
    response = Response(stream_with_context(stream_brochure()), mimetype='text/event-stream')
    response.headers['X-Accel-Buffering'] = 'no'
    response.headers['Cache-Control'] = 'no-cache'
    return response


# if __name__ == '__main__':
  #   app.run(debug=True)

if __name__ == '__main__':
    from waitress import serve
    serve(app, host='0.0.0.0', port=5000, channel_timeout=300)