from corehq.apps.es.transient_util import doc_adapter_from_index_name
from corehq.util.es.elasticsearch import TransportError

from pillowtop.checkpoints.manager import PillowCheckpoint
from pillowtop.pillow.interface import ConstructedPillow


TEST_ES_MAPPING = {
    '_meta': {
        'comment': 'You know, for tests',
        'created': '2015-10-07 @czue'
    },
    "properties": {
        "doc_type": {
            "index": "not_analyzed", "type": "string"
        },
    }
}

TEST_ES_TYPE = 'test_doc'
TEST_ES_INDEX = 'test_pillowtop_index'
TEST_ES_ALIAS = 'pillowtop_tests'


def get_pillow_doc_adapter():
    return doc_adapter_from_index_name(TEST_ES_INDEX)


def get_doc_count(es, index, refresh_first=True):
    if refresh_first:
        # we default to calling refresh since ES might have stale data
        es.indices.refresh(index)
    stats = es.indices.stats(index)
    return list(stats['indices'].values())[0]['total']['docs']['count']


def get_index_mapping(es, index, doc_type):
    try:
        return es.indices.get_mapping(index, doc_type).get(index, {}).get('mappings', {}).get(doc_type, {})
    except TransportError:
        return {}


class FakeConstructedPillow(ConstructedPillow):
    pass


def make_fake_constructed_pillow(pillow_id, checkpoint_id):
    from pillowtop.feed.mock import RandomChangeFeed
    from pillowtop.processors import LoggingProcessor

    pillow = FakeConstructedPillow(
        name=pillow_id,
        checkpoint=PillowCheckpoint(checkpoint_id, 'text'),
        change_feed=RandomChangeFeed(10),
        processor=LoggingProcessor(),
    )
    return pillow
