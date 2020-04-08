import copy

from django.conf import settings

from casexml.apps.case.models import CommCareCase
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, KafkaCheckpointEventHandler
from corehq.elastic import get_es_new
from corehq.form_processor.utils.general import should_use_sql_backend
from corehq.form_processor.backends.sql.dbaccessors import CaseReindexAccessor
from corehq.pillows.case_search import transform_case_for_elasticsearch
from corehq.pillows.mappings.reportcase_mapping import REPORT_CASE_INDEX_INFO
from corehq.util.doc_processor.sql import SqlDocumentProvider
from corehq.util.doc_processor.couch import CouchDocumentProvider
from pillowtop.checkpoints.manager import get_checkpoint_for_elasticsearch_pillow
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import ElasticProcessor
from pillowtop.reindexer.change_providers.composite import CompositeDocProvider
from pillowtop.reindexer.reindexer import ResumableBulkElasticPillowReindexer, ReindexerFactory
from .base import convert_property_dict


def report_case_filter(doc_dict):
    """
    :return: True to filter out doc
    """
    # full indexing is only enabled for select domains on an opt-in basis
    return doc_dict.get('domain', None) not in getattr(settings, 'ES_CASE_FULL_INDEX_DOMAINS', [])


def transform_case_to_report_es(doc_dict):
    doc_ret = copy.deepcopy(doc_dict)
    convert_property_dict(
        doc_ret,
        REPORT_CASE_INDEX_INFO.mapping,
        override_root_keys=['_id', 'doc_type', '_rev', '#export_tag']
    )
    return doc_ret


def get_case_to_report_es_processor():
    return ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=REPORT_CASE_INDEX_INFO,
        doc_prep_fn=transform_case_to_report_es,
        doc_filter_fn=report_case_filter,
    )


def get_report_case_to_elasticsearch_pillow(pillow_id='ReportCaseToElasticsearchPillow',
                                            num_processes=1, process_num=0, **kwargs):
    # todo; To remove after full rollout of https://github.com/dimagi/commcare-hq/pull/21329/
    assert pillow_id == 'ReportCaseToElasticsearchPillow', 'Pillow ID is not allowed to change'
    checkpoint = get_checkpoint_for_elasticsearch_pillow(pillow_id, REPORT_CASE_INDEX_INFO, topics.CASE_TOPICS)
    form_processor = ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=REPORT_CASE_INDEX_INFO,
        doc_prep_fn=transform_case_to_report_es,
        doc_filter_fn=report_case_filter,
    )
    kafka_change_feed = KafkaChangeFeed(
        topics=topics.CASE_TOPICS, client_id='report-cases-to-es', num_processes=num_processes,
        process_num=process_num
    )
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=kafka_change_feed,
        processor=form_processor,
        change_processed_event_handler=KafkaCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100, change_feed=kafka_change_feed
        ),
    )


def get_domain_case_doc_provider(domains, iteration_key):
    providers = []
    for domain in domains:
        if should_use_sql_backend(domain):
            reindex_accessor = CaseReindexAccessor(domain=domain)
            doc_provider = SqlDocumentProvider(iteration_key, reindex_accessor)
        else:
            doc_provider = CouchDocumentProvider(iteration_key, doc_type_tuples=[
                CommCareCase,
                ("CommCareCase-Deleted", CommCareCase)
            ], domain=domain)
        providers.append(doc_provider)
    return CompositeDocProvider(providers)


class ReportCaseReindexerFactory(ReindexerFactory):
    slug = 'report-case'
    arg_contributors = [
        ReindexerFactory.elastic_reindexer_args,
    ]

    def build(self):
        domains = getattr(settings, 'ES_CASE_FULL_INDEX_DOMAINS', [])
        iteration_key = "ReportCaseToElasticsearchPillow_{}_reindexer".format(REPORT_CASE_INDEX_INFO.index)
        doc_provider = get_domain_case_doc_provider(domains, iteration_key)
        return ResumableBulkElasticPillowReindexer(
            doc_provider,
            elasticsearch=get_es_new(),
            index_info=REPORT_CASE_INDEX_INFO,
            doc_transform=transform_case_for_elasticsearch,
            pillow=get_report_case_to_elasticsearch_pillow(),
            **self.options
        )
