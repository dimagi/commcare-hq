from django.conf import settings

from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, MultiTopicCheckpointEventHandler
from corehq.elastic import get_es_new
from corehq.pillows.base import convert_property_dict
from corehq.pillows.xform import transform_xform_for_elasticsearch
from corehq.util.doc_processor import CouchDocumentProvider
from couchforms.models import XFormInstance, XFormArchived, XFormError, XFormDeprecated, \
    XFormDuplicate, SubmissionErrorLog
from pillowtop.checkpoints.manager import PillowCheckpoint
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import ElasticProcessor
from pillowtop.reindexer.reindexer import ResumableBulkElasticPillowReindexer
from .mappings.reportxform_mapping import REPORT_XFORM_INDEX_INFO
from .xform import XFormPillow

COMPUTED_CASEBLOCKS_KEY = '_case_blocks'


class ReportXFormPillow(XFormPillow):
    """
    an extension to XFormPillow that provides for indexing of arbitrary data fields
    within the xform
    """
    es_alias = "report_xforms"
    es_type = "report_xform"
    es_index = REPORT_XFORM_INDEX_INFO.index

    #type level mapping
    default_mapping = REPORT_XFORM_INDEX_INFO.mapping

    def change_transform(self, doc_dict):
        if not report_xform_filter(doc_dict):
            return transform_xform_for_report_forms_index(doc_dict)


def report_xform_filter(doc_dict):
    """
    :return: True to filter out doc
    """
    domain = doc_dict.get('domain', None)
    if not domain or domain not in getattr(settings, 'ES_XFORM_FULL_INDEX_DOMAINS', []):
        # full indexing is only enabled for select domains on an opt-in basis
        return True


def transform_xform_for_report_forms_index(doc_dict):
    doc_ret = transform_xform_for_elasticsearch(doc_dict, include_props=False)
    if doc_ret:
        convert_property_dict(
            doc_ret['form'],
            REPORT_XFORM_INDEX_INFO.mapping['properties']['form'],
            override_root_keys=['case']
        )
        if 'computed_' in doc_ret:
            convert_property_dict(doc_ret['computed_'], {})

        return doc_ret
    else:
        return None


def get_report_xform_to_elasticsearch_pillow(pillow_id='ReportXFormToElasticsearchPillow'):
    checkpoint = PillowCheckpoint(
        'report-xforms-to-elasticsearch',
    )
    form_processor = ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=REPORT_XFORM_INDEX_INFO,
        doc_prep_fn=transform_xform_for_report_forms_index,
        doc_filter_fn=report_xform_filter
    )
    kafka_change_feed = KafkaChangeFeed(topics=[topics.FORM, topics.FORM_SQL], group_id='report-forms-to-es')
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=kafka_change_feed,
        processor=form_processor,
        change_processed_event_handler=MultiTopicCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100, change_feed=kafka_change_feed
        ),
    )


def get_report_xform_couch_reindexer():
    iteration_key = "ReportXFormToElasticsearchPillow_{}_reindexer".format(REPORT_XFORM_INDEX_INFO.index)
    doc_provider = CouchDocumentProvider(iteration_key, doc_types=[
        XFormInstance,
        XFormArchived,
        XFormError,
        XFormDeprecated,
        XFormDuplicate,
        ('XFormInstance-Deleted', XFormInstance),
        ('HQSubmission', XFormInstance),
        SubmissionErrorLog,
    ])
    return ResumableBulkElasticPillowReindexer(
        doc_provider,
        elasticsearch=get_es_new(),
        index_info=REPORT_XFORM_INDEX_INFO,
        doc_filter=report_xform_filter,
        doc_transform=transform_xform_for_report_forms_index,
    )
