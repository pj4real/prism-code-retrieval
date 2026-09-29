const SETTINGS_SCHEME = 'app-settings://';
const KNOWN_SECTIONS = new Set(['bluetooth', 'wifi', 'display', 'sound', 'battery', 'connectivity']);

// Builds a deeplink into the Settings app, for example app-settings://wifi?highlight=on
function buildDeeplink(section, params = {}) {
  if (!KNOWN_SECTIONS.has(section)) {
    throw new Error(`unknown settings section: ${section}`);
  }
  const query = new URLSearchParams(params).toString();
  return SETTINGS_SCHEME + section + (query ? `?${query}` : '');
}

function isSettingsDeeplink(uri) {
  return typeof uri === 'string' && uri.startsWith(SETTINGS_SCHEME);
}

function resolveDeeplink(uri) {
  if (!isSettingsDeeplink(uri)) return null;
  const [path, query = ''] = uri.slice(SETTINGS_SCHEME.length).split('?');
  return { section: path, params: Object.fromEntries(new URLSearchParams(query)) };
}

module.exports = { buildDeeplink, isSettingsDeeplink, resolveDeeplink };
