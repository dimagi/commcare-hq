from __future__ import unicode_literals


def _get_analysis(*names):
    return {
        "analyzer": {name: ANALYZERS[name] for name in names}
    }


ANALYZERS = {
    "default": {
        "type": "custom",
        "tokenizer": "whitespace",
        "filter": ["lowercase"]
    },
    "comma": {
        "type": "pattern",
        "pattern": r"\s*,\s*"
    },
    "sortable_exact": {
        "type": "custom",
        "tokenizer": "keyword",
        "filter": ["lowercase"]
    },
}

ES_ENV_SETTINGS = {
    'production': {
        'xforms': {
            "number_of_replicas": Ellipsis,
        },
        'hqcases': {
            "number_of_replicas": Ellipsis,
        },
        'hqusers': {
            "number_of_shards": 2,
            "number_of_replicas": 1,
        },
    },

    'icds': {
        'hqusers': {
            "number_of_shards": 2,
            "number_of_replicas": 1,
        },
    },
}

ES_META = {
    # Default settings for all indexes on ElasticSearch
    'default': {
        "settings": {
            "number_of_replicas": 0,
            "analysis": _get_analysis('default', 'sortable_exact'),
        },
    },
    # Default settings for aliases on all environments (overrides default settings)
    'hqdomains': {
        "settings": {
            "number_of_replicas": 0,
            "analysis": _get_analysis('default', 'comma'),
        },
    },

    'hqapps': {
        "settings": {
            "number_of_replicas": 0,
            "analysis": _get_analysis('default'),
        },
    },

    'hqusers': {
        "settings": {
            "number_of_shards": 2,
            "number_of_replicas": 0,
            "analysis": _get_analysis('default'),
        },
    },
}
