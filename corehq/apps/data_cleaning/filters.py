from abc import ABC, abstractmethod
from memoized import memoized

from django.utils.translation import gettext_lazy

from corehq.apps.data_cleaning.models import PinnedFilterType
from corehq.apps.reports.filters.case_list import CaseListFilter
from corehq.apps.reports.filters.select import SelectOpenCloseFilter


class SessionPinnedFilterMixin(ABC):

    def __init__(self, session, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = session

    @property
    @abstractmethod
    def filter_type(self):
        """
        This helps tie the report filter subclass to a pinned filter for the
        `BulkEditSession`
        :return: `PinnedFilterType`
        """
        raise NotImplementedError("please specify a filter_type")

    @property
    @memoized
    def pinned_filter(self):
        return self.session.pinned_filters.get(filter_type=self.filter_type)

    @abstractmethod
    def get_value_for_db(self):
        """
        This method is different from the original class method of
        `get_value(request, domain)` from `BaseReportFilter` and its subclasses.

        This method should return the value that will be stored as the
        `BulkEditPinnedFilter` value of the same `filter_type`.

        :return: None if the value is the default value,
            otherwise a list of at least one value
        """
        raise NotImplementedError("please implement get_value_for_db")

    def update_stored_value(self):
        value = self.get_value_for_db()
        if value != self.pinned_filter.value:
            # update the pinned filter only if the value has changed
            self.pinned_filter.value = value
            self.pinned_filter.save()


class CaseOwnersPinnedFilter(SessionPinnedFilterMixin, CaseListFilter):
    template = "data_cleaning/filters/pinned/multi_option.html"
    placeholder = gettext_lazy("Please add case owners to filter the list of cases.")
    filter_type = PinnedFilterType.CASE_OWNERS

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

    @property
    @memoized
    def selected(self):
        return self._get_selected_from_selected_ids(self.pinned_filter.value)

    @classmethod
    def _get_default_db_value(cls):
        return [s[0] for s in cls.default_selections]

    def get_value_for_db(self):
        value = self.get_value(self.request, self.domain)
        return None if value == self._get_default_db_value() else value


class CaseStatusPinnedFilter(SessionPinnedFilterMixin, SelectOpenCloseFilter):
    template = "data_cleaning/filters/pinned/single_option.html"
    filter_type = PinnedFilterType.CASE_STATUS

    @property
    def filter_context(self):
        return {
            'report_select2_config': super().filter_context,
        }

    @property
    @memoized
    def selected(self):
        return self.pinned_filter.value[0] if self.pinned_filter.value else ""

    def get_value_for_db(self):
        value = self.get_value(self.request, self.domain)
        return None if not value else [value]
