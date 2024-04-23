from corehq.apps.case_search.const import (
    INDEXED_METADATA_BY_KEY,
    METADATA_IN_REPORTS,
)
from corehq.apps.es.case_search import wrap_case_search_hit
from corehq.apps.reports.standard.cases.data_sources import CaseDisplaySQL
from corehq.const import SERVER_DATETIME_FORMAT


class CaseDataFormatter(CaseDisplaySQL):

    date_format = SERVER_DATETIME_FORMAT

    def __init__(self, raw_data, timezone):
        case = wrap_case_search_hit(raw_data)
        super().__init__(case, timezone)

    def get_context(self):
        context = {}
        context.update(self.case.to_json())
        context.update(self._case_info_context)
        context['_link'] = self.case_detail_url
        return context

    @property
    def _case_info_context(self):
        context = {}
        for prop in METADATA_IN_REPORTS:
            context[prop] = self._get_case_info_prop(prop)
        return context

    def _get_case_info_prop(self, prop):
        fmt_prop = prop.replace('@', '')
        if hasattr(self, fmt_prop):
            return getattr(self, fmt_prop)
        elif prop in INDEXED_METADATA_BY_KEY:
            return INDEXED_METADATA_BY_KEY[prop].get_value(self.raw_data)
        raise NotImplementedError("CaseDataFormatter.{} not found".format(prop))
