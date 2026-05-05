import hashlib
import json

from cachetools import TTLCache

_cache = TTLCache(maxsize=1000, ttl=300)


def make_key(filters: dict) -> str:
    canonical = json.dumps(filters, sort_keys=True)
    return hashlib.md5(canonical.encode()).hexdigest()


def get(key: str):
    return _cache.get(key)


def set(key: str, value) -> None:
    _cache[key] = value


def delete(key: str) -> None:
    _cache.pop(key, None)


def clear() -> None:
    _cache.clear()
