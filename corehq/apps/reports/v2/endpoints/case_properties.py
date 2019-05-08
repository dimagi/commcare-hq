from __future__ import absolute_import
from __future__ import unicode_literals

from memoized import memoized

from corehq.apps.case_search.const import (
    SPECIAL_CASE_PROPERTIES,
    CASE_COMPUTED_METADATA,
)
from corehq.apps.reports.standard.cases.filters import (
    get_flattened_case_properties,
)
from corehq.apps.reports.v2.models import BaseOptionsEndpoint


class CasePropertiesEndpoint(BaseOptionsEndpoint):
    slug = "case_properties"

    @property
    @memoized
    def existing_slugs(self):
        return self.report_context.get('existingSlugs', [])

    @property
    def excluded_slugs(self):
        return ['name'] + self.existing_slugs

    @property
    @memoized
    def case_properties(self):
        case_properties = get_flattened_case_properties(
            self.domain, include_parent_properties=False
        )
        special_properties = [
            {'name': prop, 'case_type': None, 'meta_type': 'info'}
            for prop in SPECIAL_CASE_PROPERTIES + CASE_COMPUTED_METADATA
        ]
        return case_properties + special_properties

    @property
    def filtered_case_properties(self):

        def _filter_property(prop):
            # todo future filters based on case_types, etc.
            return prop['name'] not in self.excluded_slugs

        return [prop for prop in self.case_properties if _filter_property(prop)]

    def get_response(self):
        return {
            'options': self.filtered_case_properties,
        }
