import functools
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop

from corehq.apps.reports import util
from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter

from corehq import feature_previews
from corehq.apps.reports.models import HQUserType
from corehq.apps.reports.standard import ProjectReport, ProjectReportParametersMixin, DatespanMixin
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.display import FormDisplay
from corehq.apps.reports.filters.forms import MISSING_APP_ID, FormsByApplicationFilter
from corehq.apps.reports.generic import (GenericTabularReport,
                                         ProjectInspectionReportParamsMixin,
                                         ElasticProjectInspectionReport)
from corehq.apps.reports.standard.monitoring import MultiFormDrilldownMixin, CompletionOrSubmissionTimeMixin
from corehq.apps.reports.util import datespan_from_beginning
from corehq.elastic import es_query, ADD_TO_ES_FILTER
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX
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


class SubmitHistoryMixin(ElasticProjectInspectionReport,
                         ProjectReportParametersMixin,
                         CompletionOrSubmissionTimeMixin, MultiFormDrilldownMixin,
                         DatespanMixin):
    name = ugettext_noop('Submit History')
    slug = 'submit_history'
    fields = [
        'corehq.apps.reports.filters.users.ExpandedMobileWorkerFilter',
        'corehq.apps.reports.filters.forms.FormsByApplicationFilter',
        'corehq.apps.reports.filters.forms.CompletionOrSubmissionTimeFilter',
        'corehq.apps.reports.filters.dates.DatespanFilter',
    ]
    ajax_pagination = True
    include_inactive = True

    # Feature preview flag for Submit History Filters
    def __init__(self, request, **kwargs):
        if feature_previews.SUBMIT_HISTORY_FILTERS.enabled(request.domain):
            # create a new instance attribute instead of modifying the
            # class attribute
            self.fields = self.fields + [
                'corehq.apps.reports.filters.forms.FormDataFilter',
                'corehq.apps.reports.filters.forms.CustomFieldFilter',
            ]
        super(SubmitHistoryMixin, self).__init__(request, **kwargs)

    @property
    def other_fields(self):
        return filter(None, self.request.GET.get('custom_field', "").split(","))

    @property
    def default_datespan(self):
        return datespan_from_beginning(self.domain, self.timezone)

    def _es_extra_filters(self):
        if FormsByApplicationFilter.has_selections(self.request):
            def form_filter(form):
                app_id = form.get('app_id', None)
                if app_id and app_id != MISSING_APP_ID:
                    return {'and': [{'term': {'xmlns.exact': form['xmlns']}},
                                    {'term': {'app_id': app_id}}]}
                return {'term': {'xmlns.exact': form['xmlns']}}
            form_values = self.all_relevant_forms.values()
            if form_values:
                yield {'or': [form_filter(f) for f in form_values]}

        truthy_only = functools.partial(filter, None)
        mobile_user_and_group_slugs = self.request.GET.getlist(ExpandedMobileWorkerFilter.slug)
        users_data = ExpandedMobileWorkerFilter.pull_users_and_groups(
            self.domain,
            mobile_user_and_group_slugs,
            simplified_users=True,
            combined=True,
            include_inactive=True
        )
        all_mobile_workers_selected = 't__0' in self.request.GET.getlist('emw')
        if not all_mobile_workers_selected or users_data.admin_and_demo_users:
            yield {
                'terms': {
                    'form.meta.userID': truthy_only(
                        u.user_id for u in users_data.combined_users
                    )
                }
            }
        else:
            negated_ids = util.get_all_users_by_domain(
                self.domain,
                user_filter=HQUserType.all_but_users(),
                simplified=True,
            )
            yield {
                'not': {
                    'terms': {
                        'form.meta.userID': truthy_only(
                            user.user_id for user in negated_ids
                        )
                    }
                }
            }

        props = truthy_only(self.request.GET.get('form_data', '').split(','))
        for prop in props:
            yield {
                'term': {'__props_for_querying': prop.lower()}
            }

    def _es_xform_filter(self):
        return ADD_TO_ES_FILTER['forms']

    def filters_as_es_query(self):
        return {
            'query': {
                'range': {
                    self.time_field: {
                        'from': self.datespan.startdate_param,
                        'to': self.datespan.enddate_param,
                        'include_upper': False,
                    }
                }
            },
            'filter': {
                'and': (self._es_xform_filter() +
                        list(self._es_extra_filters()))
            },
            'sort': self.get_sorting_block(),
        }

    @property
    @memoized
    def es_results(self):
        return es_query(
            params={'domain.exact': self.domain},
            q=self.filters_as_es_query(),
            es_url=XFORM_INDEX + '/xform/_search',
            start_at=self.pagination.start,
            size=self.pagination.count,
        )

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
        return int(self.es_results['hits']['total'])


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

        h.extend([DataTablesColumn(field) for field in self.other_fields])
        return DataTablesHeader(*h)

    @property
    def rows(self):
        submissions = [res['_source'] for res in self.es_results.get('hits', {}).get('hits', [])]

        for form in submissions:
            display = FormDisplay(form, self)
            row = [
                display.form_data_link,
                display.username,
                display.submission_or_completion_time,
                display.readable_form_name,
            ]
            if self.show_extra_columns:
                row.append(form.get('last_sync_token', ''))
            yield row + display.other_columns
