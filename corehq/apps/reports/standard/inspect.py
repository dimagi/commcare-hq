from couchdbkit.exceptions import ResourceNotFound
from couchdbkit.resource import RequestFailed
from django.core.urlresolvers import reverse, NoReverseMatch
from django.template.defaultfilters import yesno
import json
from django.utils import html
import pytz
from django.conf import settings
from casexml.apps.case.models import CommCareCase
from corehq.apps.hqcase.paginator import CasePaginator
from corehq.apps.hqsofabed.models import HQFormData
from corehq.apps.reports.standard import ProjectReport, ProjectReportParametersMixin
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.display import xmlns_to_name
from corehq.apps.reports.fields import SelectOpenCloseField, SelectMobileWorkerField
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.users.models import CommCareUser
from dimagi.utils.couch.database import get_db
from dimagi.utils.couch.pagination import CouchFilter, FilteredPaginator
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.timezones import utils as tz_utils
from corehq.apps.groups.models import Group
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop


class ProjectInspectionReportParamsMixin(object):
    @property
    def shared_pagination_GET_params(self):
        # This was moved from ProjectInspectionReport so that it could be included in CaseReassignmentInterface too
        # I tried a number of other inheritance schemes, but none of them worked because of the already
        # complicated multiple-inheritance chain
        # todo: group this kind of stuff with the field object in a comprehensive field refactor

        return [dict(name='individual', value=self.individual),
                dict(name='group', value=self.group_id),
                dict(name='case_type', value=self.case_type),
                dict(name='ufilter', value=[f.type for f in self.user_filter if f.show])]

class ProjectInspectionReport(ProjectInspectionReportParamsMixin, GenericTabularReport, ProjectReport, ProjectReportParametersMixin):
    """
        Base class for this reporting section
    """
    exportable = False
    asynchronous = False
    ajax_pagination = True
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.SelectMobileWorkerField']


class SubmitHistory(ProjectInspectionReport):
    name = ugettext_noop('Submit History')
    slug = 'submit_history'

    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn(_("View Form")),
            DataTablesColumn(_("Username")),
            DataTablesColumn(_("Submit Time")),
            DataTablesColumn(_("Form")))
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
        return "<a class='ajax_dialog' href='%(url)s'>%(text)s</a>" % {
            "url": reverse('render_form_data', args=[self.domain, instance_id]),
            "text": _("View Form")
        }


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

class CaseDisplay(object):
    def __init__(self, report, case):
        self.case = case
        self.report = report

    def user_not_found_display(self, user_id):
        return _("Unknown [%s]") % user_id

    @property
    def owner_display(self):
        username = self.report.usernames.get(self.user_id, self.user_not_found_display(self.user_id))
        if self.owning_group and self.owning_group.name:
            return '<span class="label label-inverse">%s</span>' % self.owning_group.name
        else:
            return username

    @property
    def closed_display(self):
        return yesno(self.case.closed, "closed,open")

    @property
    def case_link(self):
        case_id, case_name = self.case.case_id, self.case.name
        try:
            return html.mark_safe("<a class='ajax_dialog' href='%s'>%s</a>" % (
                html.escape(reverse('case_details', args=[self.report.domain, case_id])),
                html.escape(case_name),
            ))
        except NoReverseMatch:
            return "%s (bad ID format)" % case_name

    @property
    def case_type(self):
        return self.case.type

    @property
    def opened_on(self):
        return self.report.date_to_json(self.case.opened_on)

    @property
    def modified_on(self):
        return self.report.date_to_json(self.case.modified_on)

    @property
    def owner_id(self):
        return self.case.owner_id if self.case.owner_id else self.case.user_id

    @property
    @memoized
    def owner_doc(self):
        try:
            doc = get_db().get(self.owner_id)
        except ResourceNotFound:
            return None, None
        else:
            return {
                'CommCareUser': CommCareUser,
                'Group': Group,
            }.get(doc['doc_type']), doc

    @property
    def owner_type(self):
        owner_class, _ = self.owner_doc
        if owner_class == CommCareUser:
            return 'user'
        elif owner_class == Group:
            return 'group'
        else:
            return None

    @property
    def owner(self):
        klass, doc = self.owner_doc
        if klass:
            return klass.wrap(doc)

    @property
    def owning_group(self):
        try:
            return Group.get(self.owner_id)
        except Exception:
            return None

    @property
    def user_id(self):
        return self.report.individual or self.owner_id

    @property
    def creating_user(self):
        owner_id = ""
        for action in self.case.actions:
            if action['action_type'] == 'create':
                owner_id = action.get_user_id()
        if not owner_id:
            return _("No data")
        return self.report.usernames.get(owner_id, self.user_not_found_display(owner_id))

class CaseListMixin(ProjectInspectionReportParamsMixin, GenericTabularReport, ProjectReportParametersMixin):

    fields = [
        'corehq.apps.reports.fields.FilterUsersField',
        'corehq.apps.reports.fields.SelectCaseOwnerField',
        'corehq.apps.reports.fields.CaseTypeField',
        'corehq.apps.reports.fields.SelectOpenCloseField',
    ]
    
    @property
    @memoized
    def case_results(self):
        return CasePaginator(
            domain=self.domain,
            params=self.pagination,
            case_type=self.case_type,
            owner_ids=self.case_owners,
            user_ids=self.user_ids,
            status=self.case_status
        ).results()

    @property
    def total_records(self):
        return self.case_results['total_rows']

    @property
    @memoized
    def case_owners(self):
        if self.individual:
            group_owners = self.case_sharing_groups
        else:
            group_owners = Group.get_case_sharing_groups(self.domain)
        group_owners = [group._id for group in group_owners]
        return self.user_ids + group_owners

    @property
    @memoized
    def case_sharing_groups(self):
        try:
            user = CommCareUser.get_by_user_id(self.individual)
            user = user if user.username_in_report else None
            return user.get_case_sharing_groups()
        except Exception:
            try:
                group = Group.get(self.individual)
                assert(group.doc_type == 'Group')
                return [group]
            except Exception:
                return []

    def get_case(self, row):
        if "doc" in row:
            case = CommCareCase.wrap(row["doc"])
        elif "id" in row:
            case = CommCareCase.get(row["id"])
        else:
            raise ValueError("Can't construct case object from row result %s" % row)

        if case.domain != self.domain:
            raise Exception("case.domain != self.domain; %r and %r, respectively" % (case.domain, self.domain))

        return case


    @property
    def shared_pagination_GET_params(self):
        shared_params = super(CaseListMixin, self).shared_pagination_GET_params
        shared_params.append(dict(
            name=SelectOpenCloseField.slug,
            value=self.request.GET.get(SelectOpenCloseField.slug, '')
        ))
        return shared_params


class CaseListReport(CaseListMixin, ProjectInspectionReport):
    name = ugettext_noop('Case List')
    slug = 'case_list'

    @property
    def user_filter(self):
        return super(CaseListReport, self).user_filter

    @property
    def report_context(self):
        shared_params = super(CaseListReport, self).shared_pagination_GET_params
        rep_context = super(CaseListReport, self).report_context
        rep_context.update(
            filter=settings.LUCENE_ENABLED
        )
        return rep_context

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(_("Case Type")),
            DataTablesColumn(_("Name")),
            DataTablesColumn(_("Owner")),
            DataTablesColumn(_("Created Date")),
            DataTablesColumn(_("Created By")),
            DataTablesColumn(_("Modified Date")),
            DataTablesColumn(_("Status"))
        )
        headers.no_sort = True
        if not self.individual:
            self.name = _("%(report_name)s for %(worker_type)s") % {
                "report_name": _(self.name), 
                "worker_type": _(SelectMobileWorkerField.get_default_text(self.user_filter))
            }

        return headers

    @property
    @memoized
    def paginator_results(self):
        """This is no longer called by anything"""
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
        return paginator

    @property
    def rows(self):
        rows = []
        def _format_row(row):
            case = self.get_case(row)
            display = CaseDisplay(self, case)

            return [
                display.case_type,
                display.case_link,
                display.owner_display,
                display.opened_on,
                display.creating_user,
                display.modified_on,
                display.closed_display
            ]

        try:
            for item in self.case_results['rows']:
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

    name = ugettext_noop("Maps")
    slug = "maps"
    # todo: support some of these filters -- right now this report
    hide_filters = True
    # is more of a playground, so all the filtering is done in its
    # own ajax sidebar
    report_partial_path = "reports/partials/maps.html"
    asynchronous = False
    flush_layout = True

    @classmethod
    @memoized
    def get_config(cls, domain):
        try:
            config = get_db().view('reports/maps_config', key=[domain], include_docs=True).one()
            if config:
                config = config['doc']['config']
        except Exception:
            config = None
        return config

    @property
    def config(self):
        return self.get_config(self.domain)

    @property
    def report_context(self):
        return dict(
            maps_api_key=settings.GMAPS_API_KEY,
            case_api_url=reverse('cloudcare_get_cases', kwargs={'domain': self.domain}),
            config=json.dumps(self.config)
        )

    @classmethod
    def show_in_navigation(cls, request, domain=None):
        if cls.get_config(domain):
            return True
        else:
            return False
