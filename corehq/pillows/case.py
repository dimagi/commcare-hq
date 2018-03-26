from __future__ import absolute_import
from __future__ import unicode_literals
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
from pillowtop.reindexer.reindexer import ResumableBulkElasticPillowReindexer, ReindexerFactory

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


def get_case_to_elasticsearch_pillow(pillow_id='CaseToElasticsearchPillow', num_processes=1,
                                     process_num=0, **kwargs):
    assert pillow_id == 'CaseToElasticsearchPillow', 'Pillow ID is not allowed to change'
    checkpoint = get_checkpoint_for_elasticsearch_pillow(pillow_id, CASE_INDEX_INFO, topics.CASE_TOPICS)
    case_processor = ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=CASE_INDEX_INFO,
        doc_prep_fn=transform_case_for_elasticsearch
    )
    kafka_change_feed = KafkaChangeFeed(
        topics=topics.CASE_TOPICS, group_id='cases-to-es', num_processes=num_processes, process_num=process_num
    )
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=kafka_change_feed,
        processor=case_processor,
        change_processed_event_handler=KafkaCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100, change_feed=kafka_change_feed
        ),
    )


class CouchCaseReindexerFactory(ReindexerFactory):
    slug = 'case'
    arg_contributors = [
        ReindexerFactory.resumable_reindexer_args,
        ReindexerFactory.elastic_reindexer_args,
    ]

    def build(self):
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
            pillow=get_case_to_elasticsearch_pillow(),
            **self.options
        )


class SqlCaseReindexerFactory(ReindexerFactory):
    slug = 'sql-case'
    arg_contributors = [
        ReindexerFactory.resumable_reindexer_args,
        ReindexerFactory.elastic_reindexer_args,
        ReindexerFactory.limit_db_args,
        ReindexerFactory.domain_arg,
    ]

    def build(self):
        limit_to_db = self.options.pop('limit_to_db', None)
        domain = self.options.pop('domain', None)
        iteration_key = "SqlCaseToElasticsearchPillow_{}_reindexer_{}_{}".format(
            CASE_INDEX_INFO.index, limit_to_db or 'all', domain or 'all'
        )
        limit_db_aliases = [limit_to_db] if limit_to_db else None

        reindex_accessor = CaseReindexAccessor(domain=domain, limit_db_aliases=limit_db_aliases)
        doc_provider = SqlDocumentProvider(iteration_key, reindex_accessor)
        return ResumableBulkElasticPillowReindexer(
            doc_provider,
            elasticsearch=get_es_new(),
            index_info=CASE_INDEX_INFO,
            doc_transform=transform_case_for_elasticsearch,
            **self.options
        )
