from django.utils.translation import gettext_lazy

from corehq.apps.reports.filters.case_list import CaseListFilter
from corehq.apps.reports.filters.select import SelectOpenCloseFilter


class CaseOwnersPinnedFilter(CaseListFilter):
    template = "data_cleaning/filters/pinned/multi_option.html"
    placeholder = gettext_lazy("Please add case owners to filter the list of cases.")

    @property
    def filter_context(self):
        context = super().filter_context
        filter_help = [context.pop('filter_help_inline')]
        search_help = context.pop('search_help_inline', None)
        if search_help:
            filter_help.append(search_help)
        return {
            'report_select2_config': context,
            'filter_help': filter_help,
        }


class CaseStatusPinnedFilter(SelectOpenCloseFilter):
    template = "data_cleaning/filters/pinned/single_option.html"

    @property
    def filter_context(self):
        return {
            'report_select2_config': super().filter_context,
        }
