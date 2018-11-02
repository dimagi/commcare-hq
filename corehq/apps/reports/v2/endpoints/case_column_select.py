from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.apps.case_search.const import (
    SPECIAL_CASE_PROPERTIES,
    CASE_COMPUTED_METADATA,
)
from corehq.apps.reports.standard.cases.filters import (
    get_flattened_case_properties,
)
from corehq.apps.reports.v2.models import BaseFilterEndpoint


class CaseColumnSelectFilter(BaseFilterEndpoint):
    slug = "case_column_select"

    @property
    def case_properties(self):
        case_properties = get_flattened_case_properties(
            self.domain, include_parent_properties=False
        )
        special_properties = [
            {'name': prop, 'case_type': None, 'meta_type': 'info'}
            for prop in SPECIAL_CASE_PROPERTIES + CASE_COMPUTED_METADATA
        ]
        return case_properties + special_properties

    def get_options_response(self):
        return {
            'properties': self.case_properties,
        }

    def get_filtered_query(self, query):
        return query
