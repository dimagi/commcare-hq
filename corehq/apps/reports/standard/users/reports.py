from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from memoized import memoized

from corehq import privileges
from corehq.apps.accounting.models import BillingAccount
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.dispatcher import UserManagementReportDispatcher
from corehq.apps.reports.filters.users import (
    ChangeActionFilter,
    ChangedByUserFilter,
    EnterpriseUserFilter,
)
from corehq.apps.reports.filters.users import \
    ExpandedMobileWorkerFilter as EMWF
from corehq.apps.reports.generic import GenericTabularReport, GetParamsMixin, PaginatedReportMixin
from corehq.apps.reports.standard import DatespanMixin, ProjectReport
from corehq.apps.users.audit.change_messages import (
    ASSIGNED_LOCATIONS_FIELD,
    CHANGE_MESSAGES_FIELDS,
    DOMAIN_FIELD,
    LOCATION_FIELD,
    PHONE_NUMBERS_FIELD,
    ROLE_FIELD,
    TWO_FACTOR_FIELD,
    get_messages,
)
from corehq.apps.users.models import UserHistory
from corehq.const import USER_DATETIME_FORMAT
from corehq.util.timezones.conversions import ServerTime


class UserHistoryReport(GetParamsMixin, DatespanMixin, GenericTabularReport, ProjectReport, PaginatedReportMixin):
    slug = 'user_history'
    name = ugettext_lazy("User History")
    section_name = ugettext_lazy("User Management")

    dispatcher = UserManagementReportDispatcher

    fields = [
        'corehq.apps.reports.filters.users.AffectedUserFilter',
        'corehq.apps.reports.filters.users.ChangedByUserFilter',
        'corehq.apps.reports.filters.dates.DatespanFilter',
        'corehq.apps.reports.filters.users.ChangeActionFilter',
        'corehq.apps.reports.filters.users.UserPropertyFilter',
        'corehq.apps.reports.filters.users.UserUploadRecordFilter',
    ]

    description = ugettext_lazy("History of user updates")
    ajax_pagination = True
    default_sort = {'changed_at': 'desc'}

    @classmethod
    def get_primary_properties(cls, domain):
        """
        Get slugs and human-friendly names for the properties that are available
        for filtering and/or displayed by default in the report, without
        needing to click "See More".
        """
        if domain_has_privilege(domain, privileges.APP_USER_PROFILES):
            user_data_label = _("profile or user data")
        else:
            user_data_label = _("user data")
        return {
            "username": _("username"),
            ROLE_FIELD: _("role"),
            "email": _("email"),
            DOMAIN_FIELD: _("project"),
            "is_active": _("is active"),
            "language": _("language"),
            PHONE_NUMBERS_FIELD: _("phone numbers"),
            LOCATION_FIELD: _("primary location"),
            "user_data": user_data_label,
            TWO_FACTOR_FIELD: _("two factor authentication disabled"),
            ASSIGNED_LOCATIONS_FIELD: _("assigned locations"),
        }

    @property
    def headers(self):
        h = [
            DataTablesColumn(_("Affected User"), sortable=False),
            DataTablesColumn(_("Modified by User"), sortable=False),
            DataTablesColumn(_("Action"), prop_name='action'),
            DataTablesColumn(_("Via"), prop_name='changed_via'),
            DataTablesColumn(_("Changes"), sortable=False),
            DataTablesColumn(_("Change Message"), sortable=False),
            DataTablesColumn(_("Timestamp"), prop_name='changed_at'),
        ]

        return DataTablesHeader(*h)

    @property
    def total_records(self):
        return self._get_queryset().count()

    @memoized
    def _get_queryset(self):
        user_slugs = self.request.GET.getlist(EMWF.slug)
        user_ids = self._get_user_ids(user_slugs)
        # return empty queryset if no matching users were found
        if user_slugs and not user_ids:
            return UserHistory.objects.none()

        changed_by_user_slugs = self.request.GET.getlist(ChangedByUserFilter.slug)
        changed_by_user_ids = self._get_user_ids(changed_by_user_slugs)
        # return empty queryset if no matching users were found
        if changed_by_user_slugs and not changed_by_user_ids:
            return UserHistory.objects.none()

        user_property = self.request.GET.get('user_property')
        actions = self.request.GET.getlist('action')
        user_upload_record_id = self.request.GET.get('user_upload_record')
        query = self._build_query(user_ids, changed_by_user_ids, user_property, actions, user_upload_record_id)
        return query

    def _get_user_ids(self, slugs):
        es_query = self._get_users_es_query(slugs)
        return es_query.values_list('_id', flat=True)

    def _get_users_es_query(self, slugs):
        return EnterpriseUserFilter.user_es_query(
            self.domain,
            slugs,
            self.request.couch_user,
        )

    def _build_query(self, user_ids, changed_by_user_ids, user_property, actions, user_upload_record_id):
        filters = Q(for_domain__in=self._for_domains())

        if user_ids:
            filters = filters & Q(user_id__in=user_ids)

        if changed_by_user_ids:
            filters = filters & Q(changed_by__in=changed_by_user_ids)

        if user_property:
            filters = filters & self._get_property_filters(user_property)

        if actions and ChangeActionFilter.ALL not in actions:
            filters = filters & Q(action__in=actions)

        if user_upload_record_id:
            filters = filters & Q(user_upload_record_id=user_upload_record_id)

        if self.datespan:
            filters = filters & Q(changed_at__lt=self.datespan.enddate_adjusted,
                                  changed_at__gte=self.datespan.startdate)
        return UserHistory.objects.filter(filters)

    def _for_domains(self):
        return BillingAccount.get_account_by_domain(self.domain).get_domains()

    @staticmethod
    def _get_property_filters(user_property):
        if user_property in CHANGE_MESSAGES_FIELDS:
            query_filters = Q(change_messages__has_key=user_property)
            # to include CommCareUser creation from UI where a location can be assigned as a part of user creation
            # which is tracked only under "changes" and not "change messages"
            if user_property == LOCATION_FIELD:
                query_filters = query_filters | Q(changes__has_key='location_id')
        else:
            query_filters = Q(changes__has_key=user_property)
        return query_filters

    @property
    def rows(self):
        records = self._get_queryset().order_by(self.ordering)[
            self.pagination.start:self.pagination.start + self.pagination.count
        ]
        for record in records:
            yield self._user_history_row(record, self.domain, self.timezone)

    @property
    def ordering(self):
        by, direction = list(self.get_sorting_block()[0].items())[0]
        return '-' + by if direction == 'desc' else by

    @memoized
    def _get_location_name(self, location_id):
        from corehq.apps.locations.models import SQLLocation
        if not location_id:
            return None
        try:
            location_object = SQLLocation.objects.get(location_id=location_id)
        except ObjectDoesNotExist:
            return None
        return location_object.display_name

    def _user_history_row(self, record, domain, timezone):
        return [
            record.user_repr,
            record.changed_by_repr,
            _get_action_display(record.action),
            record.changed_via,
            self._user_history_details_cell(record.changes, domain),
            self._html_list(list(get_messages(record.change_messages))),
            ServerTime(record.changed_at).user_time(timezone).ui_string(USER_DATETIME_FORMAT),
        ]

    def _html_list(self, changes):
        items = []
        if isinstance(changes, dict):
            for key, value in changes.items():
                if isinstance(value, dict):
                    value = self._html_list(value)
                elif isinstance(value, list):
                    value = format_html(", ".join(value))
                else:
                    value = format_html(str(value))
                items.append("<li>{}: {}</li>".format(key, value))
        elif isinstance(changes, list):
            items = ["<li>{}</li>".format(format_html(change)) for change in changes]
        return mark_safe(f"<ul class='list-unstyled'>{''.join(items)}</ul>")

    def _user_history_details_cell(self, changes, domain):
        properties = UserHistoryReport.get_primary_properties(domain)
        properties.pop("user_data", None)
        primary_changes = {}
        all_changes = {}

        for key, value in changes.items():
            if key == 'location_id':
                value = self._get_location_name(value)
                primary_changes[properties[LOCATION_FIELD]] = value
                all_changes[properties[LOCATION_FIELD]] = value
            elif key == 'user_data':
                for user_data_key, user_data_value in changes['user_data'].items():
                    all_changes[f"user data: {user_data_key}"] = user_data_value
            elif key in properties:
                primary_changes[properties[key]] = value
                all_changes[properties[key]] = value
        more_count = len(all_changes) - len(primary_changes)
        return render_to_string("reports/standard/partials/user_history_changes.html", {
            "primary_changes": self._html_list(primary_changes),
            "all_changes": self._html_list(all_changes),
            "more_count": more_count,
        })


def _get_action_display(logged_action):
    action = ugettext_lazy("Updated")
    if logged_action == UserHistory.CREATE:
        action = ugettext_lazy("Added")
    elif logged_action == UserHistory.DELETE:
        action = ugettext_lazy("Deleted")
    return action
