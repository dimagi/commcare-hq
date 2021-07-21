from django.db.models import Q
from django.template.loader import render_to_string
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from memoized import memoized

from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.dispatcher import UserManagementReportDispatcher
from corehq.apps.reports.filters.users import (
    ChangeActionFilter,
    ChangedByUserFilter,
)
from corehq.apps.reports.filters.users import \
    ExpandedMobileWorkerFilter as EMWF
from corehq.apps.reports.generic import GenericTabularReport, GetParamsMixin
from corehq.apps.reports.standard import DatespanMixin, ProjectReport
from corehq.apps.users.models import UserHistory
from corehq.apps.users.util import cached_user_id_to_username
from corehq.const import USER_DATETIME_FORMAT
from corehq.util.timezones.conversions import ServerTime


class UserHistoryReport(GetParamsMixin, DatespanMixin, GenericTabularReport, ProjectReport):
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

    sortable = False

    @classmethod
    def get_primary_properties(cls, domain):
        """
        Get slugs and human-friendly names for the properties that are available
        for filtering and/or displayed by default in the report, without
        needing to click "See More".
        """
        if domain_has_privilege(domain, privileges.APP_USER_PROFILES):
            user_data_label = _("Profile or User Data")
        else:
            user_data_label = _("User Data")
        return {
            "username": _("Username"),
            "email": _("Email"),
            "domain": _("Project"),
            "is_active": _("Is Active"),
            "language": _("Language"),
            "phone_numbers": _("Phone Numbers"),
            "location_id": _("Primary Location (mobile users only)"),
            "user_data": user_data_label,
            "two_factor_auth_disabled_until": _("Two Factor Authentication Disabled"),
        }

    @property
    def headers(self):
        h = [
            DataTablesColumn(_("Affected User")),
            DataTablesColumn(_("Modified by User")),
            DataTablesColumn(_("Action")),
            DataTablesColumn(_("Via")),
            DataTablesColumn(_("Change Message")),
            DataTablesColumn(_("Changes")),
            DataTablesColumn(_("Timestamp")),
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
        return EMWF.user_es_query(
            self.domain,
            slugs,
            self.request.couch_user,
        )

    def _build_query(self, user_ids, changed_by_user_ids, user_property, actions, user_upload_record_id):
        filters = Q(domain=self.domain)

        if user_ids:
            filters = filters & Q(user_id__in=user_ids)

        if changed_by_user_ids:
            filters = filters & Q(changed_by__in=changed_by_user_ids)

        if user_property:
            filters = filters & Q(**{"details__changes__has_key": user_property})

        if actions and ChangeActionFilter.ALL not in actions:
            filters = filters & Q(action__in=actions)

        if user_upload_record_id:
            filters = filters & Q(user_upload_record_id=user_upload_record_id)

        if self.datespan:
            filters = filters & Q(changed_at__lt=self.datespan.enddate_adjusted,
                                  changed_at__gte=self.datespan.startdate)
        return UserHistory.objects.filter(filters)

    @property
    def rows(self):
        records = self._get_queryset().order_by('-changed_at')[
            self.pagination.start:self.pagination.start + self.pagination.count
        ]
        for record in records:
            yield _user_history_row(record, self.domain, self.timezone)


def _user_history_row(record, domain, timezone):
    return [
        cached_user_id_to_username(record.user_id),
        cached_user_id_to_username(record.changed_by),
        _get_action_display(record.action),
        record.details['changed_via'],
        record.message,
        _user_history_details_cell(record.details['changes'], domain),
        ServerTime(record.changed_at).user_time(timezone).ui_string(USER_DATETIME_FORMAT),
    ]


def _user_history_details_cell(changes, domain):
    def _html_list(changes, unstyled=True):
        items = []
        for key, value in changes.items():
            if isinstance(value, dict):
                value = _html_list(value, unstyled=unstyled)
            elif isinstance(value, list):
                value = format_html(", ".join(value))
            else:
                value = format_html(str(value))
            items.append("<li>{}: {}</li>".format(key, value))

        class_attr = "class='list-unstyled'" if unstyled else ""
        return mark_safe(f"<ul {class_attr}>{''.join(items)}</ul>")

    properties = UserHistoryReport.get_primary_properties(domain)
    properties.pop("user_data", None)
    primary_changes = {
        properties.get(key, key): value for key, value in changes.items()
        if key in properties
    }
    more_count = len(changes) - len(primary_changes)

    return render_to_string("reports/standard/partials/user_history_changes.html", {
        "primary_changes": _html_list(primary_changes) if primary_changes else None,
        "all_changes": _html_list(changes, unstyled=False),
        "more_count": more_count,
    })


def _get_action_display(logged_action):
    action = ugettext_lazy("Updated")
    if logged_action == UserHistory.CREATE:
        action = ugettext_lazy("Added")
    elif logged_action == UserHistory.DELETE:
        action = ugettext_lazy("Deleted")
    return action
