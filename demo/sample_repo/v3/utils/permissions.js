const GRANTED = new Set(['open_bluetooth', 'toggle_bluetooth', 'open_wifi', 'set_alarm', 'set_volume']);

async function checkPermission(toolName) {
  return GRANTED.has(toolName);
}

module.exports = { checkPermission };
