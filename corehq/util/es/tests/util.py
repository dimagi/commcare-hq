from datetime import datetime

from corehq.elastic import deregister_alias, register_alias

TEST_ES_MAPPING = {
    '_meta': {
        'comment': 'Bare bones index for ES testing',
        'created': datetime.isoformat(datetime.utcnow()),
    },
    "properties": {
        "doc_type": {
            "index": "not_analyzed", "type": "string"
        },
    }
}
TEST_ES_TYPE = 'test_es_doc'
TEST_ES_ALIAS = "test_es"


class TEST_ES_INFO:
    alias = TEST_ES_ALIAS
    type = TEST_ES_TYPE


def register_test_meta():
    register_alias(TEST_ES_INFO.alias, TEST_ES_INFO)


def deregister_test_meta():
    deregister_alias(TEST_ES_INFO.alias)


__all__ = [
    "TEST_ES_ALIAS",
    "TEST_ES_MAPPING",
    "TEST_ES_TYPE",
    "TEST_ES_INFO",
    "deregister_test_meta",
    "register_test_meta",
]
