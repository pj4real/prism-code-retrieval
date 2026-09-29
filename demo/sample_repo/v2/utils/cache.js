// Small least recently used cache backed by a Map, which keeps insertion order.
function createLruCache(limit = 100) {
  const store = new Map();
  return {
    get(key) {
      if (!store.has(key)) return undefined;
      const value = store.get(key);
      store.delete(key);
      store.set(key, value);
      return value;
    },
    set(key, value) {
      if (store.has(key)) store.delete(key);
      store.set(key, value);
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
