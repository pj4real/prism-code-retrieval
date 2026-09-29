function withTimeout(promise, ms) {
  return Promise.race([
    promise,
    new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), ms)),
  ]);
}

async function fetchJson(url, options = {}) {
  const attempts = options.retries === undefined ? 2 : options.retries;
  let lastError;
  for (let i = 0; i <= attempts; i++) {
    try {
      const response = await withTimeout(fetch(url, options), options.timeoutMs || 5000);
      if (!response.ok) {
        throw new Error(`request failed with status ${response.status}`);
      }
      return await response.json();
    } catch (err) {
      lastError = err;
    }
  }
  throw lastError;
}

// When no agent understands the request, hand it to a web search.
function fallbackToWeb(query) {
  return { agent: 'web', url: 'https://search.example.com/?q=' + encodeURIComponent(query) };
}

module.exports = { withTimeout, fetchJson, fallbackToWeb };
