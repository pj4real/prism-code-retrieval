const { fallbackToWeb } = require('../utils/http');

const AGENT_KEYWORDS = {
  connectivity: { bluetooth: 2, wifi: 2, 'wi-fi': 2, network: 1, hotspot: 2, pair: 2, nfc: 2 },
  clock: { alarm: 2, timer: 2, wake: 1, remind: 2 },
  sound: { volume: 2, mute: 2, louder: 1, quieter: 1, silent: 1 },
  display: { brightness: 2, brighter: 1, dimmer: 1, 'night mode': 3, screen: 1 },
};

// Weighted keyword score per agent. Multi word phrases count once and are
// checked before single words so 'night mode' does not need a separate rule.
function scoreAgents(utterance) {
  const text = utterance.toLowerCase();
  return Object.entries(AGENT_KEYWORDS)
    .map(([agent, words]) => ({
      agent,
      score: Object.entries(words).reduce((sum, [w, weight]) => sum + (text.includes(w) ? weight : 0), 0),
    }))
    .sort((a, b) => b.score - a.score);
}

// Picks the agent that should handle the utterance. Low confidence matches go
// to web search instead of guessing.
function routeIntent(utterance) {
  const ranked = scoreAgents(utterance);
  const [best, second] = ranked;
  if (best.score === 0 || best.score - second.score < 1) {
    return fallbackToWeb(utterance);
  }
  return { agent: best.agent, confidence: best.score / (best.score + second.score) };
}

module.exports = { scoreAgents, routeIntent };
