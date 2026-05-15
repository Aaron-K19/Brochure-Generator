def create_brochure(company_name, url):
    response = openai.chat.completions.create(
        model="gpt-4.1-mini",
        max_completion_tokens=800,
        messages=[
            {"role": "system", "content": brochure_system_prompt},
            {"role": "user", "content": get_brochure_user_prompt(company_name, url)}
        ],
    )
    result = response.choices[0].message.content
    display(Markdown(result))

# create_brochure("HuggingFace", "https://huggingface.co")

def stream_brochure(company_name, url):
    stream = openai.chat.completions.create(
        model="gpt-4.1-mini",
        max_completion_tokens=800,
        messages=[
            {"role": "system", "content": brochure_system_prompt},
            {"role": "user", "content": get_brochure_user_prompt(company_name, url)}
          ],
        stream=True
    )    
    response = ""
    display_handle = display(Markdown(""), display_id=True)
    for chunk in stream:
        response += chunk.choices[0].delta.content or ''
        update_display(Markdown(response), display_id=display_handle.display_id)

# stream_brochure("HuggingFace", "https://huggingface.co")


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

    try:
        response = openai.chat.completions.create(
            model='gpt-4.1-mini',
            max_completion_tokens=800,
            messages=[
                {'role': 'system', 'content': brochure_system_prompt},
                {'role': 'user', 'content': get_brochure_user_prompt(company_name, url, audience)}
            ]
        )
        brochure = response.choices[0].message.content
        return jsonify({'brochure': brochure})

    except Exception as e:
        return jsonify({'error': 'Something went wrong generating the brochure. Please try again.'}), 500

if __name__ == '__main__':
    app.run(debug=True)


<script>
generateBtn.addEventListener('click', async () => {
    hideError();

    const name = companyName.value.trim();
    const url  = companyUrl.value.trim();

    if (!name) { showError('Please enter a company name.'); return; }
    if (!url)  { showError('Please enter the company website URL.'); return; }

    let parsedUrl;
    try {
      parsedUrl = new URL(url.startsWith('http') ? url : 'https://' + url);
    } catch {
      showError('Please enter a valid URL, e.g. https://example.com');
      return;
    }

    setLoading(true);
    outputCard.classList.remove('visible');

    try {
      const response = await fetch('/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_name: name,
          url: parsedUrl.href,
          audience: selectedAudience
        })
      });

      const data = await response.json();

      if (!response.ok) {
        showError(data.error || 'Something went wrong. Please try again.');
        return;
      }

      audienceBadge.textContent =
        selectedAudience.charAt(0).toUpperCase() + selectedAudience.slice(1);

      outputBody.innerHTML = renderMarkdown(data.brochure);
      outputCard.classList.add('visible');
      outputCard.scrollIntoView({ behavior: 'smooth', block: 'start' });

    } catch (err) {
      showError('Unable to reach the server. Please try again shortly.');
    } finally {
      setLoading(false);
    }
  });

  function renderMarkdown(text) {
    return text
      .replace(/^### (.+)$/gm, '<h3>$1</h3>')
      .replace(/^## (.+)$/gm, '<h2>$1</h2>')
      .replace(/^# (.+)$/gm, '<h1>$1</h1>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/^- (.+)$/gm, '<li>$1</li>')
      .replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>')
      .replace(/\n\n/g, '</p><p>')
      .replace(/^(?!<[hul])/gm, '')
      .trim();
  }