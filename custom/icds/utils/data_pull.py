from datetime import datetime
from django.core.cache import cache

from custom.icds.const import (
    DATA_PULL_CACHE_KEY,
    DATA_PULL_PERMITTED_END_HOUR,
    DATA_PULL_PERMITTED_START_HOUR,
)
from custom.icds_reports.const import INDIA_TIMEZONE


def data_pull_is_in_progress():
    return cache.get(DATA_PULL_CACHE_KEY, False)


def can_initiate_data_pull():
    current_hour = datetime.now(INDIA_TIMEZONE).hour
    return (
        current_hour >= DATA_PULL_PERMITTED_START_HOUR
        and current_hour < DATA_PULL_PERMITTED_END_HOUR
    )
