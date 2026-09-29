const { buildDeeplink } = require('../utils/deeplink');
const { logEvent } = require('../utils/logger');

function setBrightness(percent) {
  const value = Math.max(1, Math.min(100, Math.round(percent)));
  logEvent('brightness_set', { value });
  return { action: 'set_brightness', value };
}

// Turns on the warm, low blue light display mode used in the evening.
function enableNightMode(startHour = 21, endHour = 6) {
  logEvent('night_mode', { startHour, endHour });
  return { action: 'night_mode', startHour, endHour, deeplink: buildDeeplink('display', {}) };
}

module.exports = { setBrightness, enableNightMode };
