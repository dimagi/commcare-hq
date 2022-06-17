import copy

from django.conf import settings

from corehq.elastic import get_es_new
from corehq.pillows.mappings.reportcase_mapping import REPORT_CASE_INDEX_INFO
from pillowtop.checkpoints.manager import get_checkpoint_for_elasticsearch_pillow
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import ElasticProcessor
from .base import convert_property_dict, is_couch_change_for_sql_domain


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
        change_filter_fn=is_couch_change_for_sql_domain
    )
