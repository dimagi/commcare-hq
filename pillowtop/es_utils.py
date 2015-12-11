
INDEX_REINDEX_SETTINGS = {
    "index": {
        "refresh_interval": "900s",
        "merge.policy.merge_factor": 20,
        "store.throttle.max_bytes_per_sec": "1mb",
        "store.throttle.type": "merge",
        "number_of_replicas": "0"
    }
}

INDEX_STANDARD_SETTINGS = {
    "index": {
        "refresh_interval": "1s",
        "merge.policy.merge_factor": 10,
        "store.throttle.max_bytes_per_sec": "5mb",
        "store.throttle.type": "node",
        "number_of_replicas": "0"
    }
}
