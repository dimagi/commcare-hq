import functools
from couchdbkit.exceptions import ResourceNotFound
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop
from corehq.util.dates import iso_string_to_datetime

from corehq.apps.reports import util
from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter

from corehq import feature_previews
from corehq.apps.reports.models import HQUserType
from corehq.apps.reports.standard import ProjectReport, ProjectReportParametersMixin, DatespanMixin
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.display import xmlns_to_name
from corehq.apps.reports.dont_use.fields import StrongFilterUsersField
from corehq.apps.reports.filters.forms import MISSING_APP_ID, FormsByApplicationFilter
from corehq.apps.reports.generic import GenericTabularReport, ProjectInspectionReportParamsMixin, ElasticProjectInspectionReport
from corehq.apps.reports.standard.monitoring import MultiFormDrilldownMixin, CompletionOrSubmissionTimeMixin
from corehq.apps.reports.util import datespan_from_beginning
from corehq.apps.users.models import CouchUser
from corehq.const import USER_DATETIME_FORMAT_WITH_SEC
from corehq.elastic import es_query, ADD_TO_ES_FILTER
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX
from corehq.util.timezones.conversions import ServerTime, PhoneTime
from corehq.util.view_utils import absolute_reverse
from dimagi.utils.couch import get_cached_property, IncompatibleDocument, safe_index
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


class SubmitHistory(ElasticProjectInspectionReport, ProjectReport,
                    ProjectReportParametersMixin,
                    CompletionOrSubmissionTimeMixin,  MultiFormDrilldownMixin,
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
    filter_users_field_class = StrongFilterUsersField
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
        super(SubmitHistory, self).__init__(request, **kwargs)

    @classmethod
    def display_in_dropdown(cls, domain=None, project=None, user=None):
        if project and project.commtrack_enabled:
            return False
        else:
            return True

    @property
    def other_fields(self):
        return filter(None, self.request.GET.get('custom_field', "").split(","))

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
        h.extend([DataTablesColumn(field) for field in self.other_fields])
        return DataTablesHeader(*h)

    @property
    def default_datespan(self):
        return datespan_from_beginning(self.domain, self.datespan_default_days, self.timezone)

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
        users_data = ExpandedMobileWorkerFilter.pull_users_and_groups(
            self.domain, self.request, True, True, include_inactive=True)
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

    @property
    @memoized
    def es_results(self):
        return es_query(
            params={'domain.exact': self.domain},
            q={
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
                    'and': (ADD_TO_ES_FILTER['forms'] +
                            list(self._es_extra_filters()))
                },
                'sort': self.get_sorting_block(),
            },
            es_url=XFORM_INDEX + '/xform/_search',
            start_at=self.pagination.start,
            size=self.pagination.count,
        )

    def get_sorting_block(self):
        sorting_block = super(SubmitHistory, self).get_sorting_block()
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

    @property
    def rows(self):
        def form_data_link(instance_id):
            return "<a class='ajax_dialog' target='_new' href='%(url)s'>%(text)s</a>" % {
                "url": absolute_reverse('render_form_data', args=[self.domain, instance_id]),
                "text": _("View Form")
            }

        submissions = [res['_source'] for res in self.es_results.get('hits', {}).get('hits', [])]

        for form in submissions:
            uid = form["form"]["meta"]["userID"]
            username = form["form"]["meta"].get("username")
            try:
                if username not in ['demo_user', 'admin']:
                    full_name = get_cached_property(CouchUser, uid, 'full_name', expiry=7*24*60*60)
                    name = '"%s"' % full_name if full_name else ""
                else:
                    name = ""
            except (ResourceNotFound, IncompatibleDocument):
                name = "<b>[unregistered]</b>"

            time = iso_string_to_datetime(safe_index(form, self.time_field.split('.')))
            if self.by_submission_time:
                user_time = ServerTime(time).user_time(self.timezone)
            else:
                user_time = PhoneTime(time, self.timezone).user_time(self.timezone)

            init_cells = [
                form_data_link(form["_id"]),
                (username or _('No data for username')) + (" %s" % name if name else ""),
                user_time.ui_string(USER_DATETIME_FORMAT_WITH_SEC),
                xmlns_to_name(self.domain, form.get("xmlns"), app_id=form.get("app_id")),
            ]

            def cell(field):
                return form["form"].get(field)
            init_cells.extend([cell(field) for field in self.other_fields])
            yield init_cells
