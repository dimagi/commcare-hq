from django.conf import settings

from corehq.elastic import SIZE_LIMIT

disallowed_settings_by_es_version = {
    2: [
        'merge.policy.merge_factor',
        'store.throttle.max_bytes_per_sec',
        'store.throttle.type',
        'search.slowlog.threshold.query.warn',
        'search.slowlog.threshold.query.info',
        'search.slowlog.threshold.query.debug',
        'search.slowlog.threshold.query.trace',
    ],
    5: [
        'merge.policy.merge_factor',
        'store.throttle.max_bytes_per_sec',
        'store.throttle.type'
    ],
}


def _get_es_settings(es_settings):
    es_settings = es_settings.copy()
    es_settings['index'].update(
        {
            # "search.slowlog.threshold.query.warn": "10s",
            # "search.slowlog.threshold.query.info": "5s",
            "search.slowlog.threshold.query.debug": "2s",
            "search.slowlog.threshold.query.trace": "500ms",
            "search.slowlog.level": "info",
        }
    )
    for setting in disallowed_settings_by_es_version[settings.ELASTICSEARCH_MAJOR_VERSION]:
        es_settings['index'].pop(setting, None)
    return es_settings


def get_reindex_es_settings():
    return _get_es_settings(
        {
            "index": {
                "refresh_interval": "1800s",
                # this property will be filtered out on ES 1
                "max_result_window": SIZE_LIMIT,
                # todo: remove these deprecated properties we are off ES 1
                "merge.policy.merge_factor": 20,
                "store.throttle.max_bytes_per_sec": "1mb",
                "store.throttle.type": "merge",
            }
        }
    )


def get_standard_es_settings():
    return _get_es_settings({
        "index": {
            "refresh_interval": "5s",
            # this property will be filtered out on ES 1
            "max_result_window": SIZE_LIMIT,
            # todo: remove these deprecated properties we are off ES 1
            "merge.policy.merge_factor": 10,
            "store.throttle.max_bytes_per_sec": "5mb",
            "store.throttle.type": "node",

        }
    })

INDEX_STANDARD_SETTINGS = get_standard_es_settings()
INDEX_REINDEX_SETTINGS = get_reindex_es_settings()
