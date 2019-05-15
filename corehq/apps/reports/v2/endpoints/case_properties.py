from __future__ import absolute_import
from __future__ import unicode_literals

from memoized import memoized

from django.utils.translation import ugettext as _

from corehq.apps.case_search.const import (
    SPECIAL_CASE_PROPERTIES,
    CASE_COMPUTED_METADATA,
)
from corehq.apps.reports.standard.cases.filters import (
    get_flattened_case_properties,
)
from corehq.apps.reports.v2.models import BaseOptionsEndpoint

DEFAULT_RESULTS_LIMIT = 10


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
    def search(self):
        return self.data.get('search', '')

    @property
    def page(self):
        return int(self.data.get('page', 1))

    @property
    def limit(self):
        return int(self.data.get('limit', DEFAULT_RESULTS_LIMIT))

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

    @staticmethod
    def _fmt_select2(prop):
        prop['text'] = prop['name']
        prop['id'] = prop['name']
        prop['labelStyle'] = ('label-default' if prop['case_type']
                              else 'label-primary')
        prop['labelText'] = prop['case_type'] or prop['meta_type']
        return prop


    @property
    @memoized
    def matching_case_properties(self):
        exact = []
        starts = []
        ends = []
        other = []

        for prop in self.case_properties:
            if prop['name'] in self.excluded_slugs:
                continue

            if not self.search:
                exact.append(self._fmt_select2(prop))

            elif prop['name'] == self.search:
                exact.append(self._fmt_select2(prop))

            elif prop['name'].startswith(self.search):
                starts.append(self._fmt_select2(prop))

            elif prop['name'].endswith(self.search):
                ends.append(self._fmt_select2(prop))

            elif self.search in prop['name']:
                other.append(self._fmt_select2(prop))

        if len(exact) == 0 and self.search:
            exact.append({
                'text': self.search,
                'id': self.search,
                'labelStyle': 'label-info',
                'labelText': '({})'.format(_("custom")),
            })

        return exact + starts + ends + other

    def get_response(self):
        #  todo more intelligent caching of results

        total = len(self.matching_case_properties)
        start = (self.page - 1) * self.limit
        stop = min(self.page * self.limit, total)
        has_more = total > stop

        matching_page = self.matching_case_properties[start:stop]

        return {
            'results': matching_page,
            'pagination': {
                'more': has_more,
            },
        }
