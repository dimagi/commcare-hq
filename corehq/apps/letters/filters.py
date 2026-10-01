from django.utils.translation import gettext_lazy

from memoized import memoized

from corehq.apps.app_manager.app_schemas.case_properties import (
    get_all_case_properties_for_case_type,
)
from corehq.apps.reports.filters.base import BaseSingleOptionFilter


class CasePropertyFilter(BaseSingleOptionFilter):
    """
    Select one property of the case type currently selected in the report's
    case type filter. Empty until a case type is applied; HQ re-renders
    filters on Apply, which is what makes this cascade.
    """

    @property
    @memoized
    def options(self):
        case_type = self.request.GET.get('case_type')
        if not case_type:
            return []
        props = get_all_case_properties_for_case_type(self.domain, case_type)
        return [(p, p) for p in props if '/' not in p]  # parent/* props aren't resolvable


class TemplatePropertyFilter(CasePropertyFilter):
    slug = 'template_property'
    label = gettext_lazy('Template ID property')
    default_text = gettext_lazy('Select case type, then Apply')


class GroupByFilter(CasePropertyFilter):
    slug = 'group_by'
    label = gettext_lazy('Group by')
    default_text = gettext_lazy('No grouping')


class SortByFilter(CasePropertyFilter):
    slug = 'sort_by'
    label = gettext_lazy('Sort by')
    default_text = gettext_lazy('Case name')
