import unittest

from lru_cache import LRUCache


class TestLRUCache(unittest.TestCase):
    def test_get_missing_returns_none(self):
        cache = LRUCache()
        self.assertIsNone(cache.get("missing"))

    def test_put_and_get(self):
        cache = LRUCache()
        cache.put("key", b"value")
        self.assertEqual(cache.get("key"), b"value")
        self.assertIn("key", cache)

    def test_get_refreshes_lru_order(self):
        cache = LRUCache(16)
        cache.put("a", b"x" * 6)
        cache.put("b", b"y" * 6)
        cache.get("a")
        cache.put("c", b"z" * 4)
        self.assertIsNone(cache.get("b"))
        self.assertEqual(cache.get("a"), b"x" * 6)
        self.assertEqual(cache.get("c"), b"z" * 4)

    def test_evicts_least_recently_used_when_over_capacity(self):
        cache = LRUCache(16)
        cache.put("a", b"x" * 6)
        cache.put("b", b"y" * 6)
        cache.put("c", b"z" * 3)
        self.assertIsNone(cache.get("a"))
        self.assertEqual(cache.get("b"), b"y" * 6)
        self.assertEqual(cache.get("c"), b"z" * 3)

    def test_oversized_entry_is_not_cached(self):
        cache = LRUCache(16)
        cache.put("big", b"x" * 16)
        self.assertNotIn("big", cache)

    def test_entry_size_includes_key_and_value(self):
        cache = LRUCache(16)
        key = "k" * 11
        cache.put(key, b"v" * 5)
        self.assertEqual(cache.get(key), b"v" * 5)

    def test_value_must_be_bytes(self):
        cache = LRUCache()
        with self.assertRaises(TypeError):
            cache.put("a", "not-bytes")


if __name__ == "__main__":
    unittest.main()
