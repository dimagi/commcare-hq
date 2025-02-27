from corehq.apps.reports.filters.case_list import CaseListFilter


class CaseOwnersPinnedFilter(CaseListFilter):
    template = "data_cleaning/filters/pinned/multi_option.html"

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
