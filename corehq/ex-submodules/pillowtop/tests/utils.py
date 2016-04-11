import sys
from select import select

from django.conf import settings
from elasticsearch import TransportError
from pillowtop.listener import AliasedElasticPillow


class TestElasticPillow(AliasedElasticPillow):
    es_alias = 'pillowtop_tests'
    es_type = 'test_doc'
    es_index = 'test_pillowtop_index'
    # just for the sake of something being here
    es_meta = {
        "settings": {
            "analysis": {
                "analyzer": {
                    "default": {
                        "type": "custom",
                        "tokenizer": "whitespace",
                        "filter": ["lowercase"]
                    },
                }
            }
        }
    }
    default_mapping = {
        '_meta': {
            'comment': 'You know, for tests',
            'created': '2015-10-07 @czue'
        },
        "properties": {
            "doc_type": {
                "index": "not_analyzed",
                "type": "string"
            },
        }
    }

    @classmethod
    def calc_meta(cls):
        # must be overridden by subclasses of AliasedElasticPillow
        return cls.es_index


def get_doc_count(es, index, refresh_first=True):
    if refresh_first:
        # we default to calling refresh since ES might have stale data
        es.indices.refresh(index)
    stats = es.indices.stats(index)
    return stats['indices'][index]['total']['docs']['count']


def get_index_mapping(es, index, doc_type):
    def _format_mapping_for_es_version(mapping):
        if settings.ELASTICSEARCH_VERSION < 1.0:
            return mapping[doc_type]
        else:
            return mapping[index]['mappings'][doc_type]
    try:
        return _format_mapping_for_es_version(es.indices.get_mapping(index, doc_type))
    except TransportError:
        return {}


def timed_raw_input(prompt, timeout=None, default="", stdout=sys.stdout):
    # http://stackoverflow.com/a/3471853/10840
    # does not work on Windows
    timeout_arg = () if timeout is None else (timeout,)
    stdout.write(prompt)
    rlist, _, _ = select([sys.stdin], [], [], *timeout_arg)
    if rlist:
        return sys.stdin.readline()
    return default
