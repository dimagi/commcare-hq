from django.conf import settings

from corehq.pillows.base import convert_property_dict
from corehq.pillows.xform import transform_xform_for_elasticsearch
from .mappings.reportxform_mapping import REPORT_XFORM_INDEX, REPORT_XFORM_MAPPING
from .xform import XFormPillow

COMPUTED_CASEBLOCKS_KEY = '_case_blocks'


class ReportXFormPillow(XFormPillow):
    """
    an extension to XFormPillow that provides for indexing of arbitrary data fields
    within the xform
    """
    es_alias = "report_xforms"
    es_type = "report_xform"
    es_index = REPORT_XFORM_INDEX

    #type level mapping
    default_mapping = REPORT_XFORM_MAPPING

    def change_transform(self, doc_dict):
        return transform_xform_for_report_forms_index(doc_dict)


def transform_xform_for_report_forms_index(doc_dict):
    doc_ret = transform_xform_for_elasticsearch(doc_dict)
    if doc_ret:
        domain = doc_dict.get('domain', None)

        if domain not in getattr(settings, 'ES_XFORM_FULL_INDEX_DOMAINS', []):
            # full indexing is only enabled for select domains on an opt-in basis
            return None
        convert_property_dict(doc_ret['form'], REPORT_XFORM_MAPPING['properties']['form'], override_root_keys=['case'])
        if 'computed_' in doc_ret:
            convert_property_dict(doc_ret['computed_'], {})

        return doc_ret
    else:
        return None
