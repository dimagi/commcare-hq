import copy
import datetime

from casexml.apps.case.models import CommCareCase
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from corehq.elastic import get_es_new
from corehq.form_processor.change_providers import SqlCaseChangeProvider
from corehq.pillows.mappings.case_mapping import CASE_MAPPING, CASE_INDEX, CASE_ES_TYPE
from corehq.pillows.utils import get_user_type
from dimagi.utils.couch import LockManager
from .base import HQPillow
import logging
from pillowtop.checkpoints.manager import PillowCheckpoint, PillowCheckpointEventHandler
from pillowtop.es_utils import doc_exists, ElasticsearchIndexInfo, get_index_info_from_pillow
from pillowtop.listener import lock_manager
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.elastic import ElasticProcessor
from pillowtop.reindexer.change_providers.couch import CouchViewChangeProvider
from pillowtop.reindexer.reindexer import get_default_reindexer_for_elastic_pillow, \
    ElasticPillowReindexer


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
    es_alias = "hqcases"
    es_type = CASE_ES_TYPE

    es_index = CASE_INDEX
    default_mapping = CASE_MAPPING

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
        index_info=ElasticsearchIndexInfo(index=CASE_INDEX, type=CASE_ES_TYPE),
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


def get_couch_case_reindexer():
    return get_default_reindexer_for_elastic_pillow(
        pillow=CasePillow(online=False),
        change_provider=CouchViewChangeProvider(
            couch_db=CommCareCase.get_db(),
            view_name='cases_by_owner/view',
            view_kwargs={
                'include_docs': True,
            }
        )
    )


def get_sql_case_reindexer():
    return ElasticPillowReindexer(
        pillow=get_sql_case_to_elasticsearch_pillow(),
        change_provider=SqlCaseChangeProvider(),
        elasticsearch=get_es_new(),
        index_info=_get_case_index_info(),
    )


def _get_case_index_info():
    return get_index_info_from_pillow(CasePillow(online=False))
