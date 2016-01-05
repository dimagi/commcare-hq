import copy
from corehq.pillows.case import CasePillow
from corehq.pillows.mappings.reportcase_mapping import REPORT_CASE_MAPPING, REPORT_CASE_INDEX
from django.conf import settings
from .base import convert_property_dict


class ReportCasePillow(CasePillow):
    """
    Simple/Common Case properties Indexer
    an extension to CasePillow that provides for indexing of custom case properties
    """
    es_alias = "report_cases"
    es_type = "report_case"
    es_index = REPORT_CASE_INDEX
    default_mapping = REPORT_CASE_MAPPING
    es_meta = {
        'settings': {
            'index.mapping.ignore_malformed': True
        }
    }

    def change_transform(self, doc_dict):
        if self.get_domain(doc_dict) not in getattr(settings, 'ES_CASE_FULL_INDEX_DOMAINS', []):
            #full indexing is only enabled for select domains on an opt-in basis
            return None
        doc_ret = copy.deepcopy(doc_dict)
        convert_property_dict(doc_ret, self.default_mapping, override_root_keys=['_id', 'doc_type', '_rev', '#export_tag'])
        return doc_ret
