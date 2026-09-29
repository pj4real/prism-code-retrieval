const { openBluetoothSettings, toggleBluetooth } = require('../tools/bluetooth');
const { openWifiSettings } = require('../tools/wifi');
const { setAlarm } = require('../tools/alarm');
const { setVolume } = require('../tools/volume');
const { checkPermission } = require('../utils/permissions');

const TOOL_TABLE = {
  open_bluetooth: openBluetoothSettings,
  toggle_bluetooth: toggleBluetooth,
  open_wifi: openWifiSettings,
  set_alarm: setAlarm,
  set_volume: setVolume,
};

// Turns a routed intent into an ordered list of tool calls.
function planSteps(intent) {
  const steps = [];
  if (intent.agent === 'connectivity' && intent.wants === 'pair') {
    steps.push({ tool: 'toggle_bluetooth', args: [true] });
    steps.push({ tool: 'open_bluetooth', args: [] });
  } else if (intent.agent === 'clock') {
    steps.push({ tool: 'set_alarm', args: [intent.time, intent.label] });
  } else if (intent.agent === 'sound') {
    steps.push({ tool: 'set_volume', args: [intent.level] });
  }
  return steps;
}

// Runs each step in order. Permission is checked before every tool call.
async function runPlan(steps) {
  const results = [];
  for (const step of steps) {
    const allowed = await checkPermission(step.tool);
    if (!allowed) {
      results.push({ tool: step.tool, skipped: true, reason: 'permission denied' });
      continue;
    }
    results.push({ tool: step.tool, output: TOOL_TABLE[step.tool](...step.args) });
  }
  return results;
}

// Retries an async operation, waiting longer after each failure.
async function retryWithBackoff(operation, attempts = 3, baseDelayMs = 200) {
  let lastError;
  for (let i = 0; i < attempts; i++) {
    try {
      return await operation();
    } catch (err) {
      lastError = err;
      await new Promise((resolve) => setTimeout(resolve, baseDelayMs * 2 ** i));
    }
  }
  throw lastError;
}

module.exports = { planSteps, runPlan, retryWithBackoff };
