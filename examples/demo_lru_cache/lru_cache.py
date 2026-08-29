# Simple LRU cache that simulates a 16-byte cache.

from collections import OrderedDict


class LRUCache:
    # A tiny LRU cache whose capacity is measured in bytes.
    def __init__(self, capacity=16):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self._cache = OrderedDict()

    @staticmethod
    def _entry_size(key, value):
        # Estimate an entry's size as key length + value length.
        return len(key) + len(value)

    def _total_size(self):
        return sum(self._entry_size(k, v) for k, v in self._cache.items())

    def get(self, key):
        # Return the value for key, or None if the key is not cached.
        if key not in self._cache:
            return None
        self._cache.move_to_end(key)
        return self._cache[key]

    def put(self, key, value):
        # Store value under key. Evict least recently used entries when the
        # total cached size would exceed the capacity.
        if not isinstance(value, bytes):
            raise TypeError("value must be bytes")
        if self._entry_size(key, value) > self.capacity:
            self._cache.pop(key, None)
            return
        self._cache[key] = value
        while self._total_size() > self.capacity:
            self._cache.popitem(last=False)

    def __contains__(self, key):
        return key in self._cache

    def __len__(self):
        return len(self._cache)
