const { stripFillerWords } = require('../utils/text');
const { routeIntent } = require('./router');

// Cleans the raw speech transcript before it is routed: normalises unicode,
// lower cases, strips punctuation and filler words, then forwards it to the router.
function normalizeUtterance(raw) {
  const folded = raw.normalize('NFKC').trim().toLowerCase();
  const noPunctuation = folded.replace(/[.,!?;:]+/g, ' ');
  const expanded = noPunctuation.replace(/\b(what|let|that)'s\b/g, '$1 is').replace(/n't\b/g, ' not');
  const cleaned = stripFillerWords(expanded.replace(/\s+/g, ' ').trim());
  return routeIntent(cleaned);
}

function askClarification(missingSlot) {
  const questions = {
    time: 'What time should I use?',
    level: 'How loud should it be?',
    ssid: 'Which network do you mean?',
  };
  return questions[missingSlot] || 'Can you say that again?';
}

// Fills slots from the utterance using a simple {slot: regex} schema.
function fillSlots(utterance, schema) {
  const filled = {};
  const missing = [];
  for (const [slot, pattern] of Object.entries(schema)) {
    const match = pattern.exec(utterance);
    if (match) filled[slot] = match[1];
    else missing.push(slot);
  }
  return { filled, missing };
}

module.exports = { normalizeUtterance, askClarification, fillSlots };
