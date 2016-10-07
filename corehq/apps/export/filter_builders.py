from datetime import timedelta

from corehq.apps.export.filters import ReceivedOnRangeFilter, GroupFormSubmittedByFilter, UserTypeFilter, OR, \
    OwnerFilter, LastModifiedByFilter, OwnerTypeFilter, ModifiedOnRangeFilter
from corehq.apps.export.forms import USER_DEMO, USER_SUPPLY
from corehq.apps.export.forms import USER_MOBILE, USER_UNKNOWN
from corehq.apps.groups.models import Group
from corehq.apps.reports.models import HQUserType
from corehq.apps.reports.util import app_export_filter, group_filter, users_filter, datespan_export_filter, \
    case_group_filter, case_users_filter, users_matching_filter
from couchexport.util import SerializableFunction
from corehq.pillows import utils


def _get_filtered_users(domain, user_types):
    user_types = _user_type_choices_to_es_user_types(user_types)
    user_filter_toggles = [
        USER_MOBILE in user_types,
        USER_DEMO in user_types,
        # The following line results in all users who match the
        # HQUserType.ADMIN filter to be included if the unknown users
        # filter is selected.
        USER_UNKNOWN in user_types,
        USER_UNKNOWN in user_types,
        USER_SUPPLY in user_types
    ]
    user_filters = HQUserType._get_manual_filterset(
        (True,) * HQUserType.count,
        user_filter_toggles
    )
    return users_matching_filter(domain, user_filters)


def _user_type_choices_to_es_user_types(choices):
    """
    Return a list of elastic search user types (each item in the return list
    is in corehq.pillows.utils.USER_TYPES) corresponding to the selected
    export user types.
    """
    es_user_types = []
    export_to_es_user_types_map = {
        USER_MOBILE: [utils.MOBILE_USER_TYPE],
        USER_DEMO: [utils.DEMO_USER_TYPE],
        USER_UNKNOWN: [
            utils.UNKNOWN_USER_TYPE, utils.SYSTEM_USER_TYPE, utils.WEB_USER_TYPE
        ],
        USER_SUPPLY: [utils.COMMCARE_SUPPLY_USER_TYPE]
    }
    for type_ in choices:
        es_user_types.extend(export_to_es_user_types_map[type_])
    return es_user_types


class BaseExportFilterBuilder(object):
    """
    A class for building export filters.
    Instantiate with selected filter options, and get the corresponding export filters with get_filters()
    """
    def __init__(self, domain, timezone, type_or_group, group, user_types, date_interval):
        """
        :param domain:
        :param timezone:
        :param type_or_group:
        :param group:
        :param user_types:
        :param date_interval: A DateSpan or DatePeriod
        """
        self.domain = domain
        self.timezone = timezone
        self.type_or_group = type_or_group
        self.group = group
        self.user_types = user_types
        self.date_interval = date_interval

    def get_filter(self):
        raise NotImplementedError


class ESFormExportFilterBuilder(BaseExportFilterBuilder):

    def get_filter(self):
        return filter(None, [
            self._get_datespan_filter(),
            self._get_group_filter(),
            self._get_user_filter()
        ])

    def _get_datespan_filter(self):
        if self.date_interval:
            try:
                if not self.date_interval.is_valid():
                    return
                self.date_interval.set_timezone(self.timezone)
            except AttributeError:
                # Some date_intervals (e.g. DatePeriod instances) don't have a set_timezone() or is_valid() method.
                pass
            return ReceivedOnRangeFilter(gte=self.date_interval.startdate, lt=self.date_interval.enddate + timedelta(days=1))

    def _get_group_filter(self):
        if self.group and self.type_or_group == "group":
            return GroupFormSubmittedByFilter(self.group)

    def _get_user_filter(self):
        if self.user_types and self.type_or_group == "users":
            return UserTypeFilter(_user_type_choices_to_es_user_types(self.user_types))


class CouchFormExportFilterBuilder(BaseExportFilterBuilder):

    def get_filter(self):
        form_filter = SerializableFunction(app_export_filter, app_id=None)
        datespan_filter = self._get_datespan_filter()
        if datespan_filter:
            form_filter &= datespan_filter
        form_filter &= self._get_user_or_group_filter()
        return form_filter

    def _get_user_or_group_filter(self):
        if self.group:
            # filter by groups
            group = Group.get(self.group)
            return SerializableFunction(group_filter, group=group)
        # filter by users
        return SerializableFunction(users_filter, users=_get_filtered_users(self.domain, self.user_types))

    def _get_datespan_filter(self):
        if self.date_interval:
            try:
                if not self.date_interval.is_valid():
                    return
                self.date_interval.set_timezone(self.timezone)
            except AttributeError:
                pass  # TODO: Explain this
            return SerializableFunction(datespan_export_filter, datespan=self.date_interval)


class ESCaseExportFilterBuilder(BaseExportFilterBuilder):

    def get_filter(self):
        if self.group:
            group = Group.get(self.group)
            user_ids = set(group.get_static_user_ids())
            case_filter = [OR(
                OwnerFilter(group._id),
                OwnerFilter(user_ids),
                LastModifiedByFilter(user_ids)
            )]
        else:
            case_sharing_groups = [g.get_id for g in Group.get_case_sharing_groups(self.domain)]
            case_filter = [OR(
                OwnerTypeFilter(_user_type_choices_to_es_user_types(self.user_types)),
                OwnerFilter(case_sharing_groups),
                LastModifiedByFilter(case_sharing_groups)
            )]

        date_filter = self._get_datespan_filter()
        if date_filter:
            case_filter.append(date_filter)

        return case_filter

    def _get_datespan_filter(self):
        if self.date_interval:
            try:
                if not self.date_interval.is_valid():
                    return
                self.date_interval.set_timezone(self.timezone)
            except AttributeError:
                pass  # TODO: Explain this
            return ModifiedOnRangeFilter(
                gte=self.date_interval.startdate, lt=self.date_interval.enddate + timedelta(days=1)
            )


class CouchCaseExportFilterBuilder(BaseExportFilterBuilder):

    def get_filter(self):
        if self.group:
            group = Group.get(self.group)
            return SerializableFunction(case_group_filter, group=group)
        case_sharing_groups = [g.get_id for g in Group.get_case_sharing_groups(self.domain)]
        return SerializableFunction(
            case_users_filter,
            users=_get_filtered_users(self.domain, self.user_types),
            groups=case_sharing_groups
        )

