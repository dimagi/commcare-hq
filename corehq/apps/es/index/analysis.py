"""Elasticsearch index analyzers and analyses.

Changes to these values must be accompanied by migrations to apply the changes
in Elasticsearch.
"""

LOWERCASE_WHITESPACE_ANALYZER = {
    "type": "custom",
    "tokenizer": "whitespace",
    "filter": ["lowercase"]
}

DEFAULT_ANALYSIS = {
    "analyzer": {
        "default": LOWERCASE_WHITESPACE_ANALYZER,
    }
}
COMMA_ANALYSIS = {
    "analyzer": {
        "default": LOWERCASE_WHITESPACE_ANALYZER,
        "comma": {
            "type": "pattern",
            "pattern": r"\s*,\s*"
        },
    }
}
PHONETIC_ANALYSIS = {
    "filter": {
        "soundex": {
            "replace": "true",
            "type": "phonetic",
            "encoder": "soundex"
        }
    },
    "analyzer": {
        "default": LOWERCASE_WHITESPACE_ANALYZER,
        "phonetic": {
            "filter": ["standard", "lowercase", "soundex"],
            "tokenizer": "standard"
        },
    }
}
