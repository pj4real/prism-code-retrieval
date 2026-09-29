// Bluetooth related tools for the voice assistant.
const { buildDeeplink } = require('../utils/deeplink');
const { logEvent } = require('../utils/logger');

// Opens the Bluetooth page inside the device Settings app.
function openBluetoothSettings() {
  const link = buildDeeplink('bluetooth', {});
  logEvent('settings_opened', { section: 'bluetooth' });
  return { action: 'open_settings', deeplink: link };
}

function toggleBluetooth(enabled) {
  if (typeof enabled !== 'boolean') {
    throw new Error('toggleBluetooth expects true or false');
  }
  logEvent('bluetooth_toggled', { enabled });
  return { action: 'set_bluetooth', enabled };
}

function listPairedDevices(deviceStore) {
  return deviceStore
    .filter((d) => d.paired)
    .map((d) => ({ name: d.name, address: d.address, connected: !!d.connected }));
}

module.exports = { openBluetoothSettings, toggleBluetooth, listPairedDevices };
