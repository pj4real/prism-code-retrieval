const { buildDeeplink } = require('../utils/deeplink');
const { logEvent } = require('../utils/logger');

function openNfcSettings() {
  return { action: 'open_settings', deeplink: buildDeeplink('connectivity', { page: 'nfc' }) };
}

function toggleNfc(enabled) {
  logEvent('nfc_toggled', { enabled });
  return { action: 'set_nfc', enabled: Boolean(enabled) };
}

module.exports = { openNfcSettings, toggleNfc };
