from __future__ import absolute_import
from __future__ import unicode_literals

import json

from memoized import memoized

from django.utils.translation import ugettext as _

from corehq.apps.app_manager.app_schemas.case_properties import (
    get_all_case_properties_for_case_type,
)
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
    def excluded_types(self):
        return [
            'name',
            '_link',
        ] + self.report_context.get('existingColumnNames', [])

    @property
    def current_value(self):
        current_value = json.loads(self.data.get('currentValue', '{}'))
        return current_value['id'] if current_value is not None else None

    @property
    def special_properties(self):
        return [
            self._fmt_result(prop, 'label-primary', _('info'))
            for prop in SPECIAL_CASE_PROPERTIES + CASE_COMPUTED_METADATA
            if prop not in self.excluded_types
        ]

    @staticmethod
    def _fmt_result(prop, style, label):
        return {
            'text': prop,
            'id': prop,
            'labelStyle': style,
            'labelText': label,
        }

    @property
    @memoized
    def case_type(self):
        from corehq.apps.reports.v2.filters.case_report import CaseTypeReportFilter
        for filter_context in self.report_context.get('reportFilters', []):
            if filter_context['name'] == CaseTypeReportFilter.name:
                return filter_context.get('value')
        return None

    @property
    @memoized
    def case_properties(self):
        if self.case_type is not None:
            case_properties = get_all_case_properties_for_case_type(
                self.domain, self.case_type
            )
            if self.current_value is not None:
                case_properties.append(self.current_value)
            case_properties = set(case_properties)
            final_properties = []
            for prop in case_properties:
                if prop == self.current_value:
                    final_properties.append(
                        self._fmt_result(prop, 'label-info', _("current"))
                    )
                elif prop not in self.excluded_types:
                    final_properties.append(
                        self._fmt_result(prop, 'label-default', self.case_type)
                    )
            return final_properties

        case_properties = get_flattened_case_properties(
            self.domain, include_parent_properties=False
        )
        property_to_types = {}
        for meta in case_properties:
            name = meta['name']

            if name in self.excluded_types:
                # skip case properties that are already added or reserved
                continue

            if name not in property_to_types:
                property_to_types[name] = []
            property_to_types[name].append(meta['case_type'])

        all_properties = []
        for name, case_types in property_to_types.items():
            if len(case_types) > 1:
                label = _("{} cases".format(len(case_types)))
            else:
                label = case_types[0]
            all_properties.append(self._fmt_result(name, 'label-default', label))

        return all_properties

    def get_response(self):
        return {
            'options': self.special_properties + self.case_properties,
        }
