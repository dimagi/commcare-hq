from corehq.apps.es import CaseES
from corehq.elastic import ES_EXPORT_INSTANCE
from custom.icds.data_management.base import ESBasedDataManagement
from custom.icds.data_management.doc_processors import (
    ResetMissingCaseNameDocProcessor,
)


class ResetMissingCaseName(ESBasedDataManagement):
    slug = "reset_missing_case_name"
    name = "Reset missing case name"
    case_type = "person"
    doc_processor = ResetMissingCaseNameDocProcessor

    def _get_case_ids(self):
        return (
            CaseES(es_instance_alias=ES_EXPORT_INSTANCE)
            .domain(self.domain)
            .case_type(self.case_type)
            .is_closed(False)
            .term('name.exact', '')
        ).get_ids()
