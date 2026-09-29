const { logEvent } = require('../utils/logger');

const STEP = 10;

function clampVolume(value) {
  if (Number.isNaN(value)) return 0;
  return Math.max(0, Math.min(100, Math.round(value)));
}

// Sets the media volume. Accepts an absolute level (0 to 100) or a relative
// change such as '+10' or '-20'.
function setVolume(level, current = 50) {
  let target = level;
  if (typeof level === 'string' && /^[+-]\d+$/.test(level)) {
    target = current + parseInt(level, 10);
  }
  const volume = clampVolume(Number(target));
  logEvent('volume_set', { volume, previous: current });
  return { action: 'set_volume', volume };
}

function stepVolume(direction, current) {
  return setVolume(current + (direction === 'up' ? STEP : -STEP), current);
}

function muteStreams(streams = ['media', 'ring', 'alarm']) {
  logEvent('volume_muted', { streams });
  return { action: 'mute', streams };
}

module.exports = { clampVolume, setVolume, stepVolume, muteStreams };
