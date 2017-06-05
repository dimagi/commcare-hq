import copy
import datetime
import logging

from casexml.apps.case.models import CommCareCase
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, KafkaCheckpointEventHandler
from corehq.elastic import get_es_new
from corehq.form_processor.backends.sql.dbaccessors import CaseReindexAccessor
from corehq.pillows.mappings.case_mapping import CASE_INDEX_INFO
from corehq.pillows.utils import get_user_type
from corehq.util.doc_processor.couch import CouchDocumentProvider
from corehq.util.doc_processor.sql import SqlDocumentProvider
from pillowtop.checkpoints.manager import get_checkpoint_for_elasticsearch_pillow
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.elastic import ElasticProcessor
from pillowtop.reindexer.reindexer import ResumableBulkElasticPillowReindexer

pillow_logging = logging.getLogger("pillowtop")
pillow_logging.setLevel(logging.INFO)


def transform_case_for_elasticsearch(doc_dict):
    doc_ret = copy.deepcopy(doc_dict)
    if not doc_ret.get("owner_id"):
        if doc_ret.get("user_id"):
            doc_ret["owner_id"] = doc_ret["user_id"]

    doc_ret['owner_type'] = get_user_type(doc_ret.get("owner_id", None))
    doc_ret['inserted_at'] = datetime.datetime.utcnow().isoformat()

    if 'backend_id' not in doc_ret:
        doc_ret['backend_id'] = 'couch'

    return doc_ret


def remove_bad_cases(doc_dict):
    # TODO: Remove this. It was added because a runaway repeater created lots
    # of form submissions against this case, filling up the change feed
    return doc_dict.get('_id') == '79f25f76-7828-4237-9f10-ca80909550f0'


def get_case_to_elasticsearch_pillow(pillow_id='CaseToElasticsearchPillow', **kwargs):
    assert pillow_id == 'CaseToElasticsearchPillow', 'Pillow ID is not allowed to change'
    checkpoint = get_checkpoint_for_elasticsearch_pillow(pillow_id, CASE_INDEX_INFO)
    case_processor = ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=CASE_INDEX_INFO,
        doc_prep_fn=transform_case_for_elasticsearch,
        doc_filter_fn=remove_bad_cases,
    )
    kafka_change_feed = KafkaChangeFeed(topics=topics.CASE_TOPICS, group_id='cases-to-es')
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=kafka_change_feed,
        processor=case_processor,
        change_processed_event_handler=KafkaCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100, change_feed=kafka_change_feed
        ),
    )


def get_couch_case_reindexer():
    iteration_key = "CouchCaseToElasticsearchPillow_{}_reindexer".format(CASE_INDEX_INFO.index)
    doc_provider = CouchDocumentProvider(iteration_key, doc_type_tuples=[
        CommCareCase,
        ("CommCareCase-Deleted", CommCareCase)
    ])
    return ResumableBulkElasticPillowReindexer(
        doc_provider,
        elasticsearch=get_es_new(),
        index_info=CASE_INDEX_INFO,
        doc_transform=transform_case_for_elasticsearch,
        pillow=get_case_to_elasticsearch_pillow()
    )


def get_sql_case_reindexer():
    iteration_key = "SqlCaseToElasticsearchPillow_{}_reindexer".format(CASE_INDEX_INFO.index)
    doc_provider = SqlDocumentProvider(iteration_key, CaseReindexAccessor())
    return ResumableBulkElasticPillowReindexer(
        doc_provider,
        elasticsearch=get_es_new(),
        index_info=CASE_INDEX_INFO,
        doc_transform=transform_case_for_elasticsearch
    )
