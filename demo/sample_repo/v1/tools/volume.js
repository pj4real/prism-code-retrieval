const { logEvent } = require('../utils/logger');

function clampVolume(value) {
  if (Number.isNaN(value)) return 0;
  return Math.max(0, Math.min(100, Math.round(value)));
}

// Sets the media volume to an absolute level between 0 and 100.
function setVolume(level) {
  const volume = clampVolume(level);
  logEvent('volume_set', { volume });
  return { action: 'set_volume', volume };
}

function muteAll() {
  logEvent('volume_muted', {});
  return { action: 'mute', streams: ['media', 'ring', 'alarm'] };
}

module.exports = { clampVolume, setVolume, muteAll };
