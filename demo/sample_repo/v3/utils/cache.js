// Least recently used cache with an optional time to live per entry.
function createLruCache(limit = 100, ttlMs = 0) {
  const store = new Map();
  const expired = (entry) => ttlMs > 0 && Date.now() - entry.storedAt > ttlMs;
  return {
    get(key) {
      if (!store.has(key)) return undefined;
      const entry = store.get(key);
      store.delete(key);
      if (expired(entry)) return undefined;
      store.set(key, entry);
      return entry.value;
    },
    set(key, value) {
      if (store.has(key)) store.delete(key);
      store.set(key, { value, storedAt: Date.now() });
      if (store.size > limit) {
        const oldest = store.keys().next().value;
        store.delete(oldest);
      }
    },
    size() {
      return store.size;
    },
  };
}

module.exports = { createLruCache };
