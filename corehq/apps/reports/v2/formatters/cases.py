from corehq.apps.case_search.const import (
    CASE_COMPUTED_METADATA,
    SPECIAL_CASE_PROPERTIES,
    SPECIAL_CASE_PROPERTIES_MAP,
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
        for prop in SPECIAL_CASE_PROPERTIES + CASE_COMPUTED_METADATA:
            context[prop] = self._get_case_info_prop(prop)
        return context

    def _get_case_info_prop(self, prop):
        fmt_prop = prop.replace('@', '')
        if hasattr(self, fmt_prop):
            return getattr(self, fmt_prop)
        elif prop in SPECIAL_CASE_PROPERTIES:
            return self._get_special_property(prop)
        raise NotImplementedError(
            "CaseDataFormatter.{} not found".format(prop))

    def _get_special_property(self, prop):
        if prop not in SPECIAL_CASE_PROPERTIES_MAP:
            return None
        return SPECIAL_CASE_PROPERTIES_MAP[prop].value_getter(self.raw_data)
