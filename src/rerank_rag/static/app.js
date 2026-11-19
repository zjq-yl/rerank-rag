const form = document.querySelector('#ask-form');
const question = document.querySelector('#question');
const rerank = document.querySelector('#use-rerank');
const retrievalOnly = document.querySelector('#retrieval-only');
const submitButton = document.querySelector('#submit-button');
const status = document.querySelector('#status');
const emptyState = document.querySelector('#empty-state');
const resultContent = document.querySelector('#result-content');
const answerSection = document.querySelector('#answer-section');
const answer = document.querySelector('#answer');
const sources = document.querySelector('#sources');
const sourceCount = document.querySelector('#source-count');

function showResults(data) {
  emptyState.hidden = true;
  resultContent.hidden = false;
  answerSection.hidden = data.answer === null;
  answer.textContent = data.answer ?? '';
  sourceCount.textContent = `(${data.hits.length})`;
  sources.replaceChildren();

  for (const [index, hit] of data.hits.entries()) {
    const card = document.createElement('article');
    card.className = 'source-card';
    const meta = document.createElement('div');
    meta.className = 'source-meta';
    const number = document.createElement('span');
    number.className = 'source-number';
    number.textContent = String(index + 1);
    const name = document.createElement('span');
    name.className = 'source-name';
    name.textContent = hit.source;
    const score = document.createElement('span');
    score.textContent = `向量分数 ${hit.score.toFixed(3)}` +
      (hit.rerank_score === undefined ? '' : ` · 重排分数 ${hit.rerank_score.toFixed(3)}`);
    const text = document.createElement('p');
    text.textContent = hit.text;
    meta.append(number, name, score);
    card.append(meta, text);
    sources.append(card);
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  submitButton.disabled = true;
  status.classList.remove('error');
  status.textContent = '正在检索文档，请稍候…';
  try {
    const response = await fetch('/api/ask', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        question: question.value,
        use_rerank: rerank.checked,
        retrieval_only: retrievalOnly.checked,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || '请求失败');
    showResults(data);
    status.textContent = retrievalOnly.checked ? '检索完成' : '回答已生成';
  } catch (error) {
    status.classList.add('error');
    status.textContent = error.message || '请求失败，请稍后重试';
  } finally {
    submitButton.disabled = false;
  }
});
