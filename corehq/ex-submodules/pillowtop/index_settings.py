from corehq.elastic import SIZE_LIMIT

INDEX_REINDEX_SETTINGS = {
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
INDEX_STANDARD_SETTINGS = {
    "index": {
        "refresh_interval": "5s",
        # this property will be filtered out on ES 1
        "max_result_window": SIZE_LIMIT,
        # todo: remove these deprecated properties we are off ES 1
        "merge.policy.merge_factor": 10,
        "store.throttle.max_bytes_per_sec": "5mb",
        "store.throttle.type": "node",

    }
}
