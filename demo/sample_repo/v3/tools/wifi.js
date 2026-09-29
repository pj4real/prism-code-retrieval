const { buildDeeplink } = require('../utils/deeplink');
const { logEvent, redactPii } = require('../utils/logger');

function openWifiSettings() {
  return { action: 'open_settings', deeplink: buildDeeplink('wifi', {}) };
}

// Connects to a saved or new wifi network. The password is never logged.
function connectToNetwork(ssid, password, options = {}) {
  if (!ssid) {
    throw new Error('ssid is required');
  }
  if (password && password.length < 8) {
    throw new Error('WPA passwords must be at least 8 characters');
  }
  logEvent('wifi_connect', redactPii({ ssid, password, hidden: !!options.hidden }));
  return { action: 'connect_wifi', ssid, secured: Boolean(password), hidden: !!options.hidden };
}

function forgetNetwork(ssid, savedNetworks) {
  const remaining = savedNetworks.filter((n) => n.ssid !== ssid);
  return { removed: savedNetworks.length - remaining.length, remaining };
}

module.exports = { openWifiSettings, connectToNetwork, forgetNetwork };
