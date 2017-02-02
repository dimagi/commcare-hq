import functools
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop, get_language

from corehq.apps.es import forms as form_es, filters as es_filters
from corehq.apps.es.users import user_ids_at_accessible_locations
from corehq.apps.hqcase.utils import SYSTEM_FORM_XMLNS
from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports import util
from corehq.apps.reports.filters.users import LocationRestrictedMobileWorkerFilter as EMWF

from corehq.apps.reports.models import HQUserType
from corehq.apps.reports.standard import ProjectReport, ProjectReportParametersMixin, DatespanMixin
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.display import FormDisplay
from corehq.apps.reports.filters.forms import FormsByApplicationFilter
from corehq.apps.reports.generic import (GenericTabularReport,
                                         ProjectInspectionReportParamsMixin,
                                         ElasticProjectInspectionReport)
from corehq.apps.reports.standard.monitoring import MultiFormDrilldownMixin, CompletionOrSubmissionTimeMixin
from corehq.apps.reports.util import datespan_from_beginning
from corehq.const import MISSING_APP_ID
from corehq.toggles import SUPPORT
from dimagi.utils.decorators.memoized import memoized


class ProjectInspectionReport(ProjectInspectionReportParamsMixin, GenericTabularReport, ProjectReport, ProjectReportParametersMixin):
    """
        Base class for this reporting section
    """
    exportable = False
    asynchronous = False
    ajax_pagination = True
    fields = ['corehq.apps.reports.filters.users.UserTypeFilter',
              'corehq.apps.reports.filters.users.SelectMobileWorkerFilter']

    def get_user_link(self, user):
        user_link = self.get_raw_user_link(user)
        return self.table_cell(user.raw_username, user_link)

    def get_raw_user_link(self, user):
        raise NotImplementedError


class SubmitHistoryMixin(ElasticProjectInspectionReport,
                         ProjectReportParametersMixin,
                         CompletionOrSubmissionTimeMixin, MultiFormDrilldownMixin,
                         DatespanMixin):
    name = ugettext_noop('Submit History')
    slug = 'submit_history'
    fields = [
        'corehq.apps.reports.filters.users.LocationRestrictedMobileWorkerFilter',
        'corehq.apps.reports.filters.forms.FormsByApplicationFilter',
        'corehq.apps.reports.filters.forms.CompletionOrSubmissionTimeFilter',
        'corehq.apps.reports.filters.dates.DatespanFilter',
    ]
    ajax_pagination = True
    include_inactive = True

    @property
    def default_datespan(self):
        return datespan_from_beginning(self.domain_object, self.timezone)

    def _get_users_filter(self, mobile_user_and_group_slugs):
        truthy_only = functools.partial(filter, None)
        users_data = EMWF.pull_users_and_groups(
            self.domain,
            mobile_user_and_group_slugs,
            include_inactive=True
        )
        selected_user_types = EMWF.selected_user_types(mobile_user_and_group_slugs)
        all_mobile_workers_selected = HQUserType.REGISTERED in selected_user_types
        if not self.request.can_access_all_locations or (not all_mobile_workers_selected or
                                                         users_data.admin_and_demo_users):
            return form_es.user_id(truthy_only(
                u.user_id for u in users_data.combined_users
            ))
        else:
            negated_ids = util.get_all_users_by_domain(
                self.domain,
                user_filter=HQUserType.all_but_users(),
                simplified=True,
            )
            return es_filters.NOT(form_es.user_id(truthy_only(
                user.user_id for user in negated_ids
            )))

    @staticmethod
    def _form_filter(form):
        app_id = form.get('app_id', None)
        if app_id and app_id != MISSING_APP_ID:
            return es_filters.AND(
                form_es.app(app_id),
                form_es.xmlns(form['xmlns'])
            )
        return form_es.xmlns(form['xmlns'])

    def scope_filter(self):
        # Filter to be applied in AND with filters for export for restricted user
        # Restricts to forms submitted by users at accessible locations
        accessible_user_ids = (user_ids_at_accessible_locations(
            self.request.domain, self.request.couch_user
        ))
        return form_es.user_id(accessible_user_ids)

    @property
    def es_query(self):
        time_filter = form_es.submitted if self.by_submission_time else form_es.completed
        mobile_user_and_group_slugs = self.request.GET.getlist(EMWF.slug)

        query = (form_es.FormES()
                 .domain(self.domain)
                 .filter(time_filter(gte=self.datespan.startdate,
                                     lt=self.datespan.enddate_adjusted))
                 .filter(self._get_users_filter(mobile_user_and_group_slugs)))

        if not self.request.can_access_all_locations:
            query = query.filter(self.scope_filter())

        # filter results by app and xmlns if applicable
        if FormsByApplicationFilter.has_selections(self.request):
            form_values = self.all_relevant_forms.values()
            if form_values:
                query = query.OR(*[self._form_filter(f) for f in form_values])

        # Exclude system forms unless they selected "Unknown User"
        if HQUserType.UNKNOWN not in EMWF.selected_user_types(mobile_user_and_group_slugs):
            query = query.NOT(form_es.xmlns(SYSTEM_FORM_XMLNS))

        return query

    @property
    @memoized
    def es_query_result(self):
        return (self.es_query
                .set_sorting_block(self.get_sorting_block())
                .start(self.pagination.start)
                .size(self.pagination.count)
                .run())

    def get_sorting_block(self):
        sorting_block = super(SubmitHistoryMixin, self).get_sorting_block()
        if sorting_block:
            return sorting_block
        else:
            return [{self.time_field: {'order': 'desc'}}]

    @property
    def time_field(self):
        return 'received_on' if self.by_submission_time else 'form.meta.timeEnd'

    @property
    def total_records(self):
        return int(self.es_query_result.total)


@location_safe
class SubmitHistory(SubmitHistoryMixin, ProjectReport):

    @property
    def show_extra_columns(self):
        return self.request.user and SUPPORT.enabled(self.request.user.username)

    @classmethod
    def display_in_dropdown(cls, domain=None, project=None, user=None):
        if project and project.commtrack_enabled:
            return False
        else:
            return True

    @property
    def headers(self):
        h = [
            DataTablesColumn(_("View Form")),
            DataTablesColumn(_("Username"), prop_name='form.meta.username'),
            DataTablesColumn(
                _("Submission Time") if self.by_submission_time
                else _("Completion Time"),
                prop_name=self.time_field
            ),
            DataTablesColumn(_("Form"), prop_name='form.@name'),
        ]
        if self.show_extra_columns:
            h.append(DataTablesColumn(_("Sync Log")))

        return DataTablesHeader(*h)

    @property
    def rows(self):
        for form in self.es_query_result.hits:
            display = FormDisplay(form, self, lang=get_language())
            row = [
                display.form_data_link,
                display.username,
                display.submission_or_completion_time,
                display.readable_form_name,
            ]

            if self.show_extra_columns:
                row.append(form.get('last_sync_token', ''))
            yield row
