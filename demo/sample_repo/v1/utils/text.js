const FILLER = new Set(['um', 'uh', 'please', 'hey', 'okay', 'like', 'just']);

function stripFillerWords(text) {
  return text
    .split(/\s+/)
    .filter((word) => !FILLER.has(word))
    .join(' ');
}

function tokenize(text) {
  return text.toLowerCase().match(/[a-z0-9]+/g) || [];
}

// Edit distance between two strings, used for fuzzy matching of network names.
function levenshtein(a, b) {
  const rows = a.length + 1;
  const cols = b.length + 1;
  const dp = Array.from({ length: rows }, (_, i) => [i, ...Array(cols - 1).fill(0)]);
  for (let j = 0; j < cols; j++) dp[0][j] = j;
  for (let i = 1; i < rows; i++) {
    for (let j = 1; j < cols; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      dp[i][j] = Math.min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost);
    }
  }
  return dp[rows - 1][cols - 1];
}

module.exports = { stripFillerWords, tokenize, levenshtein };
