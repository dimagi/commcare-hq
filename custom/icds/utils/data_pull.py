from django.core.cache import cache

from custom.icds.const import DATA_PULL_CACHE_KEY


def data_pull_is_in_progress():
    return cache.get(DATA_PULL_CACHE_KEY, False)


def set_data_pull_in_progress():
    return cache.set(DATA_PULL_CACHE_KEY, True, 60*60)


def reset_data_pull_in_progress():
    return cache.set(DATA_PULL_CACHE_KEY, False)
