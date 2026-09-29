const { fallbackToWeb } = require('../utils/http');

const AGENT_KEYWORDS = {
  connectivity: ['bluetooth', 'wifi', 'wi-fi', 'network', 'hotspot', 'pair'],
  clock: ['alarm', 'timer', 'wake', 'remind'],
  sound: ['volume', 'mute', 'louder', 'quieter', 'silent'],
};

// Counts keyword hits per agent and returns the scores sorted best first.
function scoreAgents(utterance) {
  const text = utterance.toLowerCase();
  return Object.entries(AGENT_KEYWORDS)
    .map(([agent, words]) => ({
      agent,
      score: words.reduce((sum, w) => sum + (text.includes(w) ? 1 : 0), 0),
    }))
    .sort((a, b) => b.score - a.score);
}

// Picks the agent that should handle the utterance, or sends it to web search
// when nothing matches.
function routeIntent(utterance) {
  const ranked = scoreAgents(utterance);
  if (ranked[0].score === 0) {
    return fallbackToWeb(utterance);
  }
  return { agent: ranked[0].agent, confidence: ranked[0].score / (ranked[1].score + 1) };
}

module.exports = { scoreAgents, routeIntent };
