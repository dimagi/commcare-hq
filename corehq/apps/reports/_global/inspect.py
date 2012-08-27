import logging
from couchdbkit.resource import RequestFailed
from django.core.urlresolvers import reverse, NoReverseMatch
from django.template.defaultfilters import yesno
import json
import pytz
from django.conf import settings
from django.template.defaultfilters import yesno
from casexml.apps.case.models import CommCareCase
from corehq.apps.hqsofabed.models import HQFormData
from corehq.apps.reports._global import ProjectReport, ProjectReportParametersMixin
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.display import xmlns_to_name
from corehq.apps.reports.fields import SelectOpenCloseField, SelectMobileWorkerField, CaseTypeField
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.models import HQUserType
from corehq.apps.users.models import CommCareUser
from dimagi.utils.couch.database import get_db
from dimagi.utils.couch.pagination import CouchFilter, FilteredPaginator
from dimagi.utils.timezones import utils as tz_utils
from corehq.apps.groups.models import Group

class ProjectInspectionReport(GenericTabularReport, ProjectReport, ProjectReportParametersMixin):
    """
        Base class for this reporting section
    """
    exportable = False
    asynchronous = False
    ajax_pagination = True
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.SelectMobileWorkerField']

    @property
    def shared_pagination_GET_params(self):
        return [dict(name='individual', value=self.individual),
                dict(name='group', value=self.group_name),
                dict(name='case_type', value=self.case_type),
                dict(name='ufilter', value=[f.type for f in self.user_filter if f.show])]

class SubmitHistory(ProjectInspectionReport):
    name = 'Submit History'
    slug = 'submit_history'

    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn("View Form"),
            DataTablesColumn("Username"),
            DataTablesColumn("Submit Time"),
            DataTablesColumn("Form"))
        headers.no_sort = True
        return headers

    _all_history = None
    @property
    def all_history(self):
        if self._all_history is None:
            self._all_history = HQFormData.objects.filter(userID__in=self.user_ids, domain=self.domain)
        return self._all_history

    @property
    def total_records(self):
        return self.all_history.count()

    @property
    def rows(self):
        rows = []
        all_hist = HQFormData.objects.filter(userID__in=self.user_ids, domain=self.domain)
        history = all_hist.extra(order_by=['-received_on'])[self.pagination.start:self.pagination.start+self.pagination.count]
        for data in history:
            if data.userID in self.user_ids:
                time = tz_utils.adjust_datetime_to_timezone(data.received_on, pytz.utc.zone, self.timezone.zone)
                time = time.strftime("%Y-%m-%d %H:%M:%S")
                xmlns = data.xmlns
                app_id = data.app_id
                xmlns = xmlns_to_name(self.domain, xmlns, app_id=app_id)
                rows.append([self._form_data_link(data.instanceID), self.usernames[data.userID], time, xmlns])
        return rows

    def _form_data_link(self, instance_id):
        return "<a class='ajax_dialog' href='%s'>View Form</a>" % reverse('render_form_data', args=[self.domain, instance_id])


class CaseListFilter(CouchFilter):
    view = "case/all_cases"

    def __init__(self, domain, case_owner=None, case_type=None, open_case=None):

        self.domain = domain

        key = [self.domain]
        prefix = [open_case] if open_case else ["all"]

        if case_type:
            prefix.append("type")
            key = key+[case_type]
        if case_owner:
            prefix.append("owner")
            key = key+[case_owner]

        key = [" ".join(prefix)]+key

        self._kwargs = dict(
            startkey=key,
            endkey=key+[{}],
            reduce=False
        )

    def get_total(self):
        if 'reduce' in self._kwargs:
            self._kwargs['reduce'] = True
        all_records = get_db().view(self.view,
            **self._kwargs).first()
        return all_records.get('value', 0) if all_records else 0

    def get(self, count):
        if 'reduce' in self._kwargs:
            self._kwargs['reduce'] = False
        return get_db().view(self.view,
            include_docs=True,
            limit=count,
            **self._kwargs).all()


class CaseListReport(ProjectInspectionReport):
    name = 'Case List'
    slug = 'case_list'
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.SelectCaseOwnerField',
              'corehq.apps.reports.fields.CaseTypeField']

    disable_lucene = True

    @property
    def no_lucene(self):
        return not settings.LUCENE_ENABLED or self.disable_lucene

    @property
    def override_fields(self):
        if self.no_lucene:
            return ['corehq.apps.reports.fields.SelectCaseOwnerField',
                    'corehq.apps.reports.fields.CaseTypeField',
                    'corehq.apps.reports.fields.SelectOpenCloseField']
        return super(CaseListReport, self).override_fields

    _case_sharing_groups = None
    @property
    def case_sharing_groups(self):
        if self._case_sharing_groups is None:
            try:
                user = CommCareUser.get_by_user_id(self.individual)
                user = user if user.username_in_report else None
                self._case_sharing_groups = user.get_case_sharing_groups() if user else []
            except Exception:
                self._case_sharing_groups = []
        return self._case_sharing_groups

    @property
    def user_filter(self):
        if self.no_lucene:
            self._user_filter = HQUserType.use_defaults(show_all=True)
        return super(CaseListReport, self).user_filter

    @property
    def report_context(self):
        rep_context = super(CaseListReport, self).report_context
        rep_context.update(
            filter=settings.LUCENE_ENABLED
        )
        return rep_context

    @property
    def shared_pagination_GET_params(self):
        shared_params = super(CaseListReport, self).shared_pagination_GET_params
        shared_params.append(dict(
            name=SelectOpenCloseField.slug,
            value=self.request.GET.get(SelectOpenCloseField.slug, '')
        ))
        if self.disable_lucene:
            shared_params.append(dict(name='no_lucene', value=self.disable_lucene))
        return shared_params

    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn("Name"),
            DataTablesColumn("User"),
            DataTablesColumn("Created Date"),
            DataTablesColumn("Modified Date"),
            DataTablesColumn("Status"))
        headers.no_sort = True
        if not self.individual:
            self.name = "%s for %s" % (self.name, SelectMobileWorkerField.get_default_text(self.user_filter))
        if not self.case_type:
            headers.prepend_column(DataTablesColumn("Case Type"))
        open, all = CaseTypeField.get_case_counts(self.domain, self.case_type, self.user_ids)
        if all > 0:
            self.name = "%s (%s/%s open)" % (self.name, open, all)
        else:
            self.name = "%s (empty)" % self.name
        return headers

    _paginator_results = None
    @property
    def paginator_results(self):
        if self._paginator_results is None:
            def _compare_cases(x, y):
                x = x.get('key', [])
                y = y.get('key', [])
                try:
                    x = x[-1]
                    y = y[-1]
                except Exception:
                    x = ""
                    y = ""
                return cmp(x, y)
            is_open = self.request.GET.get(SelectOpenCloseField.slug)
            filters = [CaseListFilter(self.domain, case_owner, case_type=self.case_type, open_case=is_open)
                       for case_owner in self.case_owners]
            paginator = FilteredPaginator(filters, _compare_cases)
            self._paginator_results = paginator
        return self._paginator_results

    _case_results = None
    @property
    def case_results(self):
        if self._case_results is None:
            if self.no_lucene:
                # Paginated Non-Lucene Results
                results = self.paginator_results.get(self.pagination.start, self.pagination.count)
            else:
                # Lucene Results
                # todo fix this
                search_key = self.request_params.get("sSearch", "")
                query = "domain:(%s)" % self.domain
                query = "%s AND owner_id:(%s)" % (query, " OR ".join(self.case_owners))
                if self.case_type:
                    query = "%s AND type:%s" % (query, self.case_type)
                if search_key:
                    query = "(%s) AND %s" % (search_key, query)
                results = get_db().search("case/search",
                    q=query,
                    handler="_fti/_design",
                    limit=self.pagination.start,
                    skip=self.pagination.count,
                    sort="\sort_modified"
                )
            self._case_results = results
        return self._case_results

    @property
    def total_records(self):
        return self.paginator_results.total if self.no_lucene else self.case_results.total_rows

    _case_owners = None
    @property
    def case_owners(self):
        if self._case_owners is None:
            if self.no_lucene:
                case_owners = [self.individual]+[group._id for group in self.case_sharing_groups]
            else:
                group_owners = self.case_sharing_groups if self.individual else Group.get_case_sharing_groups(self.domain)
                group_owners = [group._id for group in group_owners]
                case_owners = self.userIDs + group_owners
            self._case_owners = case_owners
        return self._case_owners


    @property
    def rows(self):
        rows = []

        def _format_row(row):
            if "doc" in row:
                case = CommCareCase.wrap(row["doc"])
            elif "id" in row:
                case = CommCareCase.get(row["id"])
            else:
                raise ValueError("Can't construct case object from row result %s" % row)

            if case.domain != self.domain:
                logging.error("case.domain != self.domain; %r and %r, respectively" % (case.domain, self.domain))

            assert(case.domain == self.domain)

            owner_id = case.owner_id if case.owner_id else case.user_id
            owning_group = None
            try:
                owning_group = Group.get(owner_id)
            except Exception:
                pass

            user_id = self.individual if self.individual else owner_id
            case_owner = self.usernames.get(user_id, "Unknown [%s]" % user_id)

            if owning_group and owning_group.name:
                if self.individual:
                    case_owner = '%s <span class="label label-inverse">%s</span>' % (case_owner, owning_group.name)
                else:
                    case_owner = '%s <span class="label label-inverse">Group</span>' % owning_group.name


            return ([] if self.case_type else [case.type]) + [
                self.case_data_link(row['id'], case.name),
                case_owner,
                self.date_to_json(case.opened_on),
                self.date_to_json(case.modified_on),
                yesno(case.closed, "closed,open")
            ]

        try:
            for item in self.case_results:
                row = _format_row(item)
                if row is not None:
                    rows.append(row)
        except RequestFailed:
            pass

        return rows

    def date_to_json(self, date):
        return tz_utils.adjust_datetime_to_timezone\
            (date, pytz.utc.zone, self.timezone.zone).strftime\
            ('%Y-%m-%d %H:%M:%S') if date else ""

    def case_data_link(self, case_id, case_name):
        try:
            return "<a class='ajax_dialog' href='%s'>%s</a>" %\
                   (reverse('case_details', args=[self.domain, case_id]),
                    case_name)
        except NoReverseMatch:
            return "%s (bad ID format)" % case_name


class MapReport(ProjectReport, ProjectReportParametersMixin):
    """
HOW TO CONFIGURE THIS REPORT

create a couch doc as such:

{
  "doc_type": "MapsReportConfig",
  "domain": <domain>,
  "config": {
    "case_types": [
      // for each case type

      {
        "case_type": <commcare case type>,
        "display_name": <display name of case type>,

        // either of the following two fields
        "geo_field": <case property for a geopoint question>,
        "geo_linked_to": <geo-enabled case type that this case links to>,

        "fields": [
          // for each reportable field

          "field": <case property>, // or one of the following magic values:
                 // "_count" -- report on the number of cases of this type
          "display_name": <display name for field>,
          "type": <datatype for field>, // can be "numeric", "enum", or "num_discrete" (enum with numeric values)

          // if type is "numeric" or "num_discrete"
          // these control the rendering of numeric data points (all are optional)
          "scale": <N>, // if absent, scale is calculated dynamically based on the max value in the field
          "color": <css color>,

          // if type is "enum" or "num_discrete" (optional, but recommended)
          "values": [
            // for each multiple-choice value

            {
              "value": <data value>,
              "label": <display name>, //optional
              "color": <css color>, //optional
            },
          ]
        ]
      },
    ]
  }
}
"""

    name = "Maps"
    slug = "maps"
    # todo: support some of these filters -- right now this report
    hide_filters = True
    # is more of a playground, so all the filtering is done in its
    # own ajax sidebar
    report_partial_path = "reports/partials/maps.html"
    asynchronous = False
    flush_layout = True

    @property
    def report_context(self):
        config = get_db().view('reports/maps_config', key=[self.domain], include_docs=True).one()
        if config:
            config = config['doc']['config']
        return dict(
            maps_api_key=settings.GMAPS_API_KEY,
            case_api_url=reverse('cloudcare_get_cases', kwargs={'domain': self.domain}),
            config=json.dumps(config)
        )