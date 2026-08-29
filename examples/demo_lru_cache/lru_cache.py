class LRUCache:
    def __init__(self, capacity=16):
        self.capacity = capacity

    @staticmethod
    def _entry_size(key, value):
        raise NotImplementedError

    def _total_size(self):
        raise NotImplementedError

    def get(self, key):
        raise NotImplementedError

    def put(self, key, value):
        raise NotImplementedError

    def __contains__(self, key):
        raise NotImplementedError

    def __len__(self):
        raise NotImplementedError
