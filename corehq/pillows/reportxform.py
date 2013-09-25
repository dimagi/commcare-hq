import copy

from django.conf import settings

from casexml.apps.case.xform import extract_case_blocks
from corehq.pillows.base import convert_properties
from .mappings.reportxform_mapping import REPORT_XFORM_INDEX, REPORT_XFORM_MAPPING
from .xform import XFormPillow


class ReportXFormPillow(XFormPillow):
    """
    an extension to XFormPillow that provides for indexing of arbitrary data fields
    within the xform

    NOTE: supersedes FullXFormPillow
    """
    es_index_prefix = "report_xforms"
    es_alias = "report_xforms"
    es_type = "report_xform"
    es_index = REPORT_XFORM_INDEX

    #type level mapping
    default_mapping = REPORT_XFORM_MAPPING

    def change_transform(self, doc_dict):
        doc_ret = super(ReportXFormPillow, self).change_transform(doc_dict)

        if doc_ret:
            domain = self.get_domain(doc_dict)

            if domain not in getattr(settings, 'ES_XFORM_FULL_INDEX_DOMAINS', []):
                #full indexing is only enabled for select domains on an opt-in basis
                return None

            #after basic transforms for stupid type mistakes are done, walk all properties.
            convert_properties(doc_ret['form'], self.default_mapping['properties']['form'], override_root_keys=['case'])
            return doc_ret
        else:
            return None



