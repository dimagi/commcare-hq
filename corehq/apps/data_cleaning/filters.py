from abc import ABC, abstractmethod
from memoized import memoized

from django.utils.translation import gettext_lazy

from corehq.apps.data_cleaning.models import PinnedFilterType
from corehq.apps.es import cases as case_es
from corehq.apps.reports.filters.case_list import CaseListFilter
from corehq.apps.reports.filters.select import SelectOpenCloseFilter
from corehq.apps.reports.standard.cases.utils import (
    all_project_data_filter,
    deactivated_case_owners,
    get_case_owners,
    query_location_restricted_cases,
)
from corehq.apps.users.models import CouchUser


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

    @classmethod
    def filter_query(cls, query, pinned_filter):
        """
        This method should return a filtered `ESQuery` object based on the value
        stored in the database.

        This will be called by the `filter_query(query)` function of
        the `BulkEditPinnedFilter` instance.

        :param query: an `ESQuery` instance (e.g. `CaseSearchQuery`)
        :param pinned_filter: Instance of `BulkEditPinnedFilter`
        :return: `ESQuery` of the same type as `query`
        """
        raise NotImplementedError("please implement `filter_query")

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

    @classmethod
    def filter_query(cls, query, pinned_filter):
        """
        todo: it would be nice to de-duplicate the logic here
        with the logic in CaseListReport, but we can address that at a later date.
        """
        couch_user = CouchUser.get_by_username(pinned_filter.session.user.username)
        domain = pinned_filter.session.domain
        can_access_all_locations = couch_user.has_permission(
            domain, 'access_all_locations'
        )
        emwf_slugs = pinned_filter.value or cls._get_default_db_value()

        if can_access_all_locations and cls.show_all_data(emwf_slugs):
            # don't apply any case owner filters
            return query

        case_owner_filters = []

        if can_access_all_locations and cls.show_project_data(emwf_slugs):
            case_owner_filters.append(
                all_project_data_filter(domain, emwf_slugs)
            )

        if can_access_all_locations and cls.show_deactivated_data(emwf_slugs):
            case_owner_filters.append(deactivated_case_owners(domain))

        if (
            cls.selected_user_ids(emwf_slugs)
            or cls.selected_user_types(emwf_slugs)
            or cls.selected_group_ids(emwf_slugs)
            or cls.selected_location_ids(emwf_slugs)
        ):
            case_owners = get_case_owners(
                can_access_all_locations, domain, emwf_slugs
            )
            if case_owners:
                case_owner_filters.append(case_es.owner(case_owners))

        if case_owner_filters:
            query = query.OR(*case_owner_filters)

        if not can_access_all_locations:
            query = query_location_restricted_cases(
                query, domain, couch_user,
            )

        return query


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

    @classmethod
    def filter_query(cls, query, pinned_filter):
        case_status = pinned_filter.value
        if case_status:
            # the `pinned_filter` values are always stored in an `ArrayField`,
            # and the value is either a list or `None`,
            # so we need to call `case_status[0]`
            query = query.is_closed(case_status[0] == 'closed')
        return query
