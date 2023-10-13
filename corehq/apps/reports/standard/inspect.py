from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop

from memoized import memoized

from corehq.apps.es import filters as es_filters
from corehq.apps.es import forms as form_es
from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.display import FormDisplay
from corehq.apps.reports.filters.forms import FormsByApplicationFilter
from corehq.apps.reports.filters.users import \
    ExpandedMobileWorkerFilter as EMWF
from corehq.apps.reports.generic import ElasticProjectInspectionReport
from corehq.apps.reports.models import HQUserType
from corehq.apps.reports.standard import (
    DatespanMixin,
    ProjectReport,
    ProjectReportParametersMixin,
)
from corehq.apps.reports.standard.monitoring import (
    CompletionOrSubmissionTimeMixin,
    MultiFormDrilldownMixin,
)
from corehq.apps.reports.util import datespan_from_beginning
from corehq.apps.users.util import SYSTEM_USER_ID
from corehq.const import MISSING_APP_ID
from corehq.toggles import SUPPORT


class SubmitHistoryMixin(ElasticProjectInspectionReport,
                         ProjectReportParametersMixin,
                         CompletionOrSubmissionTimeMixin, MultiFormDrilldownMixin,
                         DatespanMixin):
    name = gettext_noop('Submit History')
    slug = 'submit_history'
    fields = [
        'corehq.apps.reports.filters.users.ExpandedMobileWorkerFilter',
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
        if (
            EMWF.no_filters_selected(mobile_user_and_group_slugs)
            and self.request.couch_user.has_permission(self.domain, 'access_all_locations')
        ):
            return None

        user_ids = (EMWF.user_es_query(self.domain,
                                       mobile_user_and_group_slugs,
                                       self.request.couch_user)
                    .values_list('_id', flat=True))
        if HQUserType.UNKNOWN in EMWF.selected_user_types(mobile_user_and_group_slugs):
            user_ids.append(SYSTEM_USER_ID)

        return form_es.user_id(user_ids)

    @staticmethod
    def _form_filter(form):
        app_id = form.get('app_id', None)
        if app_id and app_id != MISSING_APP_ID:
            return es_filters.AND(
                form_es.app(app_id),
                form_es.xmlns(form['xmlns'])
            )
        return form_es.xmlns(form['xmlns'])

    @property
    def es_query(self):
        time_filter = form_es.submitted if self.by_submission_time else form_es.completed
        mobile_user_and_group_slugs = self.request.GET.getlist(EMWF.slug)

        query = (form_es.FormES()
                 .domain(self.domain)
                 .filter(time_filter(gte=self.datespan.startdate,
                                     lt=self.datespan.enddate_adjusted)))

        users_filter = self._get_users_filter(mobile_user_and_group_slugs)
        if users_filter:
            query = query.filter(users_filter)

        # filter results by app and xmlns if applicable
        if FormsByApplicationFilter.has_selections(self.request):
            form_values = list(self.all_relevant_forms.values())
            if form_values:
                query = query.OR(*[self._form_filter(f) for f in form_values])
        else:
            query = query.NOT(es_filters.missing("app_id"))

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

    @classmethod
    def get_subpages(cls):
        def _get_form_name(request=None, **context):
            if 'instance' in context:
                try:
                    return context['instance'].form_data['@name']
                except KeyError:
                    pass
            return _('View Form')

        from corehq.apps.reports.views import FormDataView
        return [
            {
                'title': _get_form_name,
                'urlname': FormDataView.urlname,
            },
        ]

    @property
    def headers(self):
        h = [
            DataTablesColumn(_("View Form"), css_class="view-form-link"),
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
