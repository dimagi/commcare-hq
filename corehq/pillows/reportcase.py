import copy
from corehq.pillows.case import CasePillow
from corehq.pillows.mappings.report_case_mapping import REPORT_CASE_MAPPING, REPORT_CASE_INDEX
from .base import convert_properties


class ReportCasePillow(CasePillow):
    """
    Simple/Common Case properties Indexer
    """
    es_index_prefix = "report_cases"
    es_alias = "report_cases"
    es_type = "report_case"
    es_index = REPORT_CASE_INDEX
    default_mapping = REPORT_CASE_MAPPING

    def change_transform(self, doc_dict):
        doc_ret = copy.deepcopy(doc_dict)
        convert_properties(doc_ret, self.default_mapping, override_root_keys=['_id', 'doc_type', '_rev', '#export_tag'])
        return doc_ret
