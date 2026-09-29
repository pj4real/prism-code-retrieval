const SENSITIVE_KEYS = ['password', 'token', 'secret', 'pin'];

// Replaces the values of sensitive keys so they never reach the logs.
function redactPii(payload) {
  const copy = { ...payload };
  for (const key of Object.keys(copy)) {
    if (SENSITIVE_KEYS.some((s) => key.toLowerCase().includes(s))) {
      copy[key] = '[redacted]';
    }
  }
  return copy;
}

function logEvent(name, payload = {}) {
  const line = JSON.stringify({ t: Date.now(), event: name, ...payload });
  console.log(line);
  return line;
}

module.exports = { redactPii, logEvent };
