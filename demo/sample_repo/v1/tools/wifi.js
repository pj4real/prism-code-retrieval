const { buildDeeplink } = require('../utils/deeplink');
const { logEvent, redactPii } = require('../utils/logger');

function openWifiSettings() {
  return { action: 'open_settings', deeplink: buildDeeplink('wifi', {}) };
}

// Connects to a saved or new wifi network. The password is never logged.
function connectToNetwork(ssid, password) {
  if (!ssid) {
    throw new Error('ssid is required');
  }
  logEvent('wifi_connect', redactPii({ ssid, password }));
  return { action: 'connect_wifi', ssid, secured: Boolean(password) };
}

function forgetNetwork(ssid, savedNetworks) {
  const remaining = savedNetworks.filter((n) => n.ssid !== ssid);
  return { removed: savedNetworks.length - remaining.length, remaining };
}

module.exports = { openWifiSettings, connectToNetwork, forgetNetwork };
