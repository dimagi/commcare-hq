import copy

from django.conf import settings

from casexml.apps.case.models import CommCareCase
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, MultiTopicCheckpointEventHandler
from corehq.elastic import get_es_new
from corehq.pillows.case import CasePillow
from corehq.pillows.mappings.reportcase_mapping import REPORT_CASE_INDEX_INFO
from pillowtop.checkpoints.manager import PillowCheckpoint
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import ElasticProcessor
from pillowtop.reindexer.reindexer import ResumableBulkElasticPillowReindexer
from .base import convert_property_dict


class ReportCasePillow(CasePillow):
    """
    Simple/Common Case properties Indexer
    an extension to CasePillow that provides for indexing of custom case properties
    """
    es_alias = "report_cases"
    es_type = "report_case"
    es_index = REPORT_CASE_INDEX_INFO.index
    default_mapping = REPORT_CASE_INDEX_INFO.mapping

    @classmethod
    def get_unique_id(cls):
        return '8c10a7564b6af5052f8b86693bf6ac07'

    def change_transform(self, doc_dict):
        if not report_case_filter(doc_dict):
            return transform_case_to_report_es(doc_dict)


def report_case_filter(doc_dict):
    """
        :return: True to filter out doc
    """
    if doc_dict.get('domain', None) not in getattr(settings, 'ES_CASE_FULL_INDEX_DOMAINS', []):
        # full indexing is only enabled for select domains on an opt-in basis
        return True


def transform_case_to_report_es(doc_dict):
    doc_ret = copy.deepcopy(doc_dict)
    convert_property_dict(
        doc_ret,
        REPORT_CASE_INDEX_INFO.mapping,
        override_root_keys=['_id', 'doc_type', '_rev', '#export_tag']
    )
    return doc_ret


def get_report_case_to_elasticsearch_pillow(pillow_id='ReportCaseToElasticsearchPillow'):
    checkpoint = PillowCheckpoint(
        'report-cases-to-elasticsearch',
    )
    form_processor = ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=REPORT_CASE_INDEX_INFO,
        doc_prep_fn=transform_case_to_report_es,
        doc_filter_fn=report_case_filter,
    )
    kafka_change_feed = KafkaChangeFeed(topics=[topics.CASE, topics.CASE_SQL], group_id='report-cases-to-es')
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=kafka_change_feed,
        processor=form_processor,
        change_processed_event_handler=MultiTopicCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100, change_feed=kafka_change_feed
        ),
    )


def get_report_case_couch_reindexer():
    return ResumableBulkElasticPillowReindexer(
        name='ReportCaseToElasticsearchPillow',
        doc_types=[CommCareCase],
        elasticsearch=get_es_new(),
        index_info=REPORT_CASE_INDEX_INFO,
        doc_filter=report_case_filter,
        doc_transform=transform_case_to_report_es,
    )
