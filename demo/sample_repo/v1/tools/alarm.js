const { logEvent } = require('../utils/logger');

let nextAlarmId = 1;
const alarms = new Map();

// Turns phrases like "7:30 pm" or "in 20 minutes" into a Date.
function parseTimeExpression(text, now = new Date()) {
  const relative = /in\s+(\d+)\s*(minute|min|hour|hr)s?/i.exec(text);
  if (relative) {
    const amount = parseInt(relative[1], 10);
    const unit = relative[2].toLowerCase().startsWith('h') ? 60 : 1;
    return new Date(now.getTime() + amount * unit * 60000);
  }
  const clock = /(\d{1,2})(?::(\d{2}))?\s*(am|pm)?/i.exec(text);
  if (!clock) return null;
  let hours = parseInt(clock[1], 10);
  const minutes = clock[2] ? parseInt(clock[2], 10) : 0;
  const meridiem = (clock[3] || '').toLowerCase();
  if (meridiem === 'pm' && hours < 12) hours += 12;
  if (meridiem === 'am' && hours === 12) hours = 0;
  const target = new Date(now);
  target.setHours(hours, minutes, 0, 0);
  if (target <= now) target.setDate(target.getDate() + 1);
  return target;
}

function setAlarm(timeText, label = 'Alarm') {
  const when = parseTimeExpression(timeText);
  if (!when) {
    return { ok: false, reason: 'could not understand the time' };
  }
  const id = nextAlarmId++;
  alarms.set(id, { id, when, label });
  logEvent('alarm_set', { id, when: when.toISOString() });
  return { ok: true, id, when };
}

function cancelAlarm(id) {
  const existed = alarms.delete(id);
  return { ok: existed };
}

module.exports = { parseTimeExpression, setAlarm, cancelAlarm };
