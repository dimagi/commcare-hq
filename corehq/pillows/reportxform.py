from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf import settings

from corehq.elastic import get_es_new
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, KafkaCheckpointEventHandler
from corehq.pillows.base import convert_property_dict
from corehq.pillows.mappings.reportxform_mapping import REPORT_XFORM_INDEX_INFO
from corehq.pillows.xform import transform_xform_for_elasticsearch, xform_pillow_filter
from pillowtop.checkpoints.manager import get_checkpoint_for_elasticsearch_pillow
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import ElasticProcessor
from pillowtop.reindexer.change_providers.form import get_domain_form_change_provider
from pillowtop.reindexer.reindexer import ElasticPillowReindexer, ReindexerFactory


def report_xform_filter(doc_dict):
    """
    :return: True to filter out doc
    """
    domain = doc_dict.get('domain', None)
    # full indexing is only enabled for select domains on an opt-in basis
    return xform_pillow_filter(doc_dict) or domain not in getattr(settings, 'ES_XFORM_FULL_INDEX_DOMAINS', [])


def transform_xform_for_report_forms_index(doc_dict):
    doc_ret = transform_xform_for_elasticsearch(doc_dict)
    convert_property_dict(
        doc_ret['form'],
        REPORT_XFORM_INDEX_INFO.mapping['properties']['form'],
        override_root_keys=['case']
    )
    if 'computed_' in doc_ret:
        convert_property_dict(doc_ret['computed_'], {})

    return doc_ret


def get_report_xform_to_elasticsearch_pillow(pillow_id='ReportXFormToElasticsearchPillow', num_processes=1,
                                             process_num=0, **kwargs):
    # todo; To remove after full rollout of https://github.com/dimagi/commcare-hq/pull/21329/
    assert pillow_id == 'ReportXFormToElasticsearchPillow', 'Pillow ID is not allowed to change'
    checkpoint = get_checkpoint_for_elasticsearch_pillow(pillow_id, REPORT_XFORM_INDEX_INFO, topics.FORM_TOPICS)
    form_processor = ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=REPORT_XFORM_INDEX_INFO,
        doc_prep_fn=transform_xform_for_report_forms_index,
        doc_filter_fn=report_xform_filter
    )
    kafka_change_feed = KafkaChangeFeed(
        topics=topics.FORM_TOPICS, client_id='report-forms-to-es',
        num_processes=num_processes, process_num=process_num
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


class ReportFormReindexerFactory(ReindexerFactory):
    slug = 'report-xform'
    arg_contributors = [
        ReindexerFactory.elastic_reindexer_args,
    ]

    def build(self):
        """Returns a reindexer that will only reindex data from enabled domains
        """
        domains = getattr(settings, 'ES_XFORM_FULL_INDEX_DOMAINS', [])
        change_provider = get_domain_form_change_provider(domains=domains)
        return ElasticPillowReindexer(
            pillow_or_processor=get_report_xform_to_elasticsearch_pillow(),
            change_provider=change_provider,
            elasticsearch=get_es_new(),
            index_info=REPORT_XFORM_INDEX_INFO,
            **self.options
        )
