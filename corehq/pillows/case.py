import copy
import datetime
import logging

from casexml.apps.case.models import CommCareCase
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from corehq.elastic import get_es_new
from corehq.form_processor.change_providers import SqlCaseChangeProvider
from corehq.pillows.mappings.case_mapping import CASE_INDEX_INFO
from corehq.pillows.utils import get_user_type
from dimagi.utils.couch import LockManager
from pillowtop.checkpoints.manager import PillowCheckpoint, PillowCheckpointEventHandler
from pillowtop.es_utils import doc_exists
from pillowtop.listener import lock_manager
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.elastic import ElasticProcessor
from pillowtop.reindexer.reindexer import ElasticPillowReindexer, ResumableBulkElasticPillowReindexer
from .base import HQPillow

UNKNOWN_DOMAIN = "__nodomain__"
UNKNOWN_TYPE = "__notype__"


pillow_logging = logging.getLogger("pillowtop")
pillow_logging.setLevel(logging.INFO)


class CasePillow(HQPillow):
    """
    Simple/Common Case properties Indexer
    """
    document_class = CommCareCase
    couch_filter = "case/casedocs"
    es_alias = CASE_INDEX_INFO.alias
    es_type = CASE_INDEX_INFO.type

    es_index = CASE_INDEX_INFO.index
    default_mapping = CASE_INDEX_INFO.mapping

    @classmethod
    def get_unique_id(cls):
        # TODO: remove this next time the index name changes
        return '85e1a25ff57c5892b6fa95caf949ae4c'

    def change_trigger(self, changes_dict):
        doc_dict, lock = lock_manager(
            super(CasePillow, self).change_trigger(changes_dict)
        )
        if doc_dict and doc_dict['doc_type'] == 'CommCareCase-Deleted':
            if doc_exists(self, doc_dict):
                self.get_es_new().delete(self.es_index, self.es_type, doc_dict['_id'])
            return None
        else:
            return LockManager(doc_dict, lock)

    def change_transform(self, doc_dict):
        return transform_case_for_elasticsearch(doc_dict)


def transform_case_for_elasticsearch(doc_dict):
    doc_ret = copy.deepcopy(doc_dict)
    if not doc_ret.get("owner_id"):
        if doc_ret.get("user_id"):
            doc_ret["owner_id"] = doc_ret["user_id"]

    doc_ret['owner_type'] = get_user_type(doc_ret.get("owner_id", None))
    doc_ret['inserted_at'] = datetime.datetime.utcnow().isoformat()

    return doc_ret


def get_sql_case_to_elasticsearch_pillow(pillow_id='SqlCaseToElasticsearchPillow'):
    checkpoint = PillowCheckpoint(
        'sql-cases-to-elasticsearch',
    )
    case_processor = ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=CASE_INDEX_INFO,
        doc_prep_fn=transform_case_for_elasticsearch
    )
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=KafkaChangeFeed(topics=[topics.CASE_SQL], group_id='sql-cases-to-es'),
        processor=case_processor,
        change_processed_event_handler=PillowCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100,
        ),
    )


def get_couch_case_to_elasticsearch_pillow(pillow_id='CouchCaseToElasticsearchPillow'):
    checkpoint = PillowCheckpoint(
        'couch-cases-to-elasticsearch',
    )
    case_processor = ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=CASE_INDEX_INFO,
        doc_prep_fn=transform_case_for_elasticsearch
    )
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=KafkaChangeFeed(topics=[topics.CASE], group_id='couch-cases-to-es'),
        processor=case_processor,
        change_processed_event_handler=PillowCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100,
        ),
    )


def get_couch_case_reindexer():
    return ResumableBulkElasticPillowReindexer(
        name="CouchCaseToElasticsearchPillow",
        doc_types=[CommCareCase],
        elasticsearch=get_es_new(),
        index_info=CASE_INDEX_INFO,
        doc_transform=transform_case_for_elasticsearch
    )


def get_sql_case_reindexer():
    return ElasticPillowReindexer(
        pillow=get_sql_case_to_elasticsearch_pillow(),
        change_provider=SqlCaseChangeProvider(),
        elasticsearch=get_es_new(),
        index_info=CASE_INDEX_INFO,
    )
