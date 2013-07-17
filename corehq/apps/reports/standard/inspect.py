from datetime import datetime
import json

from couchdbkit.exceptions import ResourceNotFound
from couchdbkit.resource import RequestFailed
import dateutil
from django.core.urlresolvers import reverse, NoReverseMatch
from django.template.defaultfilters import yesno
from django.utils import html
from django.utils.safestring import mark_safe
import pytz
from django.conf import settings
from django.core import cache
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop
import simplejson

from casexml.apps.case.models import CommCareCaseAction
from corehq.apps.api.es import CaseES
from corehq.apps.hqsofabed.models import HQFormData
from corehq.apps.reports.filters.search import SearchFilter
from corehq.apps.reports.filters.select import SelectOpenCloseFilter
from corehq.apps.reports.filters.users import SelectMobileWorkerFilter, StrongUserTypeFilter
from corehq.apps.reports.standard import ProjectReport, ProjectReportParametersMixin, DatespanMixin
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericTabularReport, ProjectInspectionReportParamsMixin, ElasticProjectInspectionReport
from corehq.apps.reports.standard.monitoring import MultiFormDrilldownMixin
from corehq.apps.users.models import CommCareUser, CouchUser
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX
from dimagi.utils.couch import get_cached_property
from dimagi.utils.couch.database import get_db
from dimagi.utils.couch.pagination import CouchFilter
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.timezones import utils as tz_utils
from corehq.apps.groups.models import Group



class ProjectInspectionReport(ProjectInspectionReportParamsMixin, GenericTabularReport, ProjectReport, ProjectReportParametersMixin):
    """
        Base class for this reporting section
    """
    exportable = False
    asynchronous = False
    ajax_pagination = True
    fields = ['corehq.apps.reports.filters.users.UserTypeFilter',
              'corehq.apps.reports.filters.users.SelectMobileWorkerFilter']


class SubmitHistory(ElasticProjectInspectionReport, ProjectReport, ProjectReportParametersMixin, MultiFormDrilldownMixin, DatespanMixin):
    name = ugettext_noop('Submit History')
    slug = 'submit_history'
    fields = [
      'corehq.apps.reports.filters.users.CombinedSelectUsersFilter',
      'corehq.apps.reports.filters.forms.FormsByApplicationFilter',
      'corehq.apps.reports.filters.dates.DatespanFilter'
    ]
    ajax_pagination = True
    filter_users_field_class = StrongUserTypeFilter
    include_inactive = True


    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn(_("View Form")),
            DataTablesColumn(_("Username"), prop_name="form.meta.username"),
            DataTablesColumn(_("Submit Time"), prop_name="form.meta.timeEnd"),
            DataTablesColumn(_("Form"), prop_name="form.@name"))
        return headers

    @property
    def es_results(self):
        if not getattr(self, 'es_response', None):
            self.es_query()
        return self.es_response

    def es_query(self):
        from corehq.apps.appstore.views import es_query
        if not getattr(self, 'es_response', None):
            q = {
                "query": {
                    "range": {
                        "form.meta.timeEnd": {
                            "from": self.datespan.startdate_param,
                            "to": self.datespan.enddate_param}}},
                "filter": {"and": []}}

            xmlnss = filter(None, [f["xmlns"] for f in self.all_relevant_forms.values()])
            if xmlnss:
                q["filter"]["and"].append({"terms": {"xmlns.exact": xmlnss}})

            def any_in(a, b):
                return any(i in b for i in a)
            if self.request.GET.get('all_mws', 'off') != 'on' or any_in(['1', '2', '3'], self.request.GET.getlist('ufilter')):
                q["filter"]["and"].append({"terms": {"form.meta.userID": filter(None, self.combined_user_ids)}})
            else:
                ids = filter(None, [user['user_id'] for user in self.get_admins_and_demo_users()])
                q["filter"]["and"].append({"not": {"terms": {"form.meta.userID": ids}}})

            q["sort"] = self.get_sorting_block() if self.get_sorting_block() else [{"form.meta.timeEnd" : {"order": "desc"}}]
            self.es_response = es_query(params={"domain.exact": self.domain}, q=q, es_url=XFORM_INDEX + '/xform/_search',
                start_at=self.pagination.start, size=self.pagination.count)
        return self.es_response

    @property
    def total_records(self):
        return int(self.es_results['hits']['total'])

    @property
    def rows(self):
        def form_data_link(instance_id):
            return "<a class='ajax_dialog' href='%(url)s'>%(text)s</a>" % {
                "url": reverse('render_form_data', args=[self.domain, instance_id]),
                "text": _("View Form")
            }

        submissions = [res['_source'] for res in self.es_results.get('hits', {}).get('hits', [])]

        for form in submissions:
            uid = form["form"]["meta"]["userID"]
            username = form["form"]["meta"].get("username")
            try:
                name = ('"%s"' % get_cached_property(CouchUser, uid, 'full_name', expiry=7*24*60*60)) \
                    if username not in ['demo_user', 'admin'] else ""
            except ResourceNotFound:
                name = "<b>[unregistered]</b>"

            yield [
                form_data_link(form["_id"]),
                (username or _('No data for username')) + (" %s" % name if name else ""),
                datetime.strptime(form["form"]["meta"]["timeEnd"], '%Y-%m-%dT%H:%M:%SZ').strftime("%Y-%m-%d %H:%M:%S"),
                form["form"].get('@name') or _('No data for form name'),
            ]

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
        """
        case is a dict object of the case doc
        """
        self.case = case
        self.report = report

    def parse_date(self, date_string):
        try:
            date_obj = dateutil.parser.parse(date_string)
            return date_obj
        except:
            return date_string

    def user_not_found_display(self, user_id):
        return _("Unknown [%s]") % user_id

    @memoized
    def _get_username(self, user_id):
        username = self.report.usernames.get(user_id)
        if not username:
            mc = cache.get_cache('default')
            cache_key = "%s.%s" % (CouchUser.__class__.__name__, user_id)

            try:
                if mc.has_key(cache_key):
                    user_dict = simplejson.loads(mc.get(cache_key))
                else:
                    user_obj = CouchUser.get_by_user_id(user_id) if user_id else None
                    if user_obj:
                        user_dict = user_obj.to_json()
                    else:
                        user_dict = {}
                    cache_payload = simplejson.dumps(user_dict)
                    mc.set(cache_key, cache_payload)
                if user_dict == {}:
                    return self.user_not_found_display(user_id)
                else:
                    user_obj = CouchUser.wrap(user_dict)
                    username = user_obj.username
            except Exception:
                return self.user_not_found_display(user_id)
        return username

    @property
    def owner_display(self):
        if self.owning_group and self.owning_group.name:
            return '<span class="label label-inverse">%s</span>' % self.owning_group.name
        else:
            return self._get_username(self.user_id)

    @property
    def closed_display(self):
        return yesno(self.case['closed'], "closed,open")

    @property
    def case_link(self):
        case_id, case_name = self.case['_id'], self.case['name']
        try:
            return html.mark_safe("<a class='ajax_dialog' href='%s'>%s</a>" % (
                html.escape(reverse('case_details', args=[self.report.domain, case_id])),
                html.escape(case_name),
            ))
        except NoReverseMatch:
            return "%s (bad ID format)" % case_name

    @property
    def case_type(self):
        return self.case['type']

    @property
    def opened_on(self):
        return self.report.date_to_json(self.parse_date(self.case['opened_on']))

    @property
    def modified_on(self):
        return self.report.date_to_json(self.modified_on_dt)

    @property
    def modified_on_dt(self):
        return self.parse_date(self.case['modified_on'])

    @property
    def owner_id(self):
        if 'owner_id' in self.case:
            return self.case['owner_id']
        elif 'user_id' in self.case:
            return self.case['user_id']
        else:
            return ''

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
        mc = cache.get_cache('default')
        cache_key = "%s.%s" % (Group.__class__.__name__, self.owner_id)
        try:
            if mc.has_key(cache_key):
                cached_obj = simplejson.loads(mc.get(cache_key))
                wrapped = Group.wrap(cached_obj)
                return wrapped
            else:
                group_obj = Group.get(self.owner_id)
                mc.set(cache_key, simplejson.dumps(group_obj.to_json()))
                return group_obj
        except Exception:
            return None

    @property
    def user_id(self):
        return self.report.individual or self.owner_id

    @property
    def creating_user(self):
        creator_id = None
        for action in self.case['actions']:
            if action['action_type'] == 'create':
                action_doc = CommCareCaseAction.wrap(action)
                creator_id = action_doc.get_user_id()
                break
        if not creator_id:
            return _("No data")
        return self._get_username(creator_id)


class CaseSearchFilter(SearchFilter):
    search_help_inline = mark_safe(ugettext_noop("""Search any text, or use a targeted query. For more info see the <a href='https://wiki.commcarehq.org/display/commcarepublic/Advanced+Case+Search' target='_blank'>Case Search</a> help page"""))


class CaseListMixin(ElasticProjectInspectionReport, ProjectReportParametersMixin):
    fields = [
        'corehq.apps.reports.filters.users.UserTypeFilter',
        'corehq.apps.reports.filters.users.SelectCaseOwnerFilter',
        'corehq.apps.reports.filters.select.CaseTypeFilter',
        'corehq.apps.reports.filters.select.SelectOpenCloseFilter',
        'corehq.apps.reports.standard.inspect.CaseSearchFilter',
    ]

    case_filter = {}
    ajax_pagination = True
    asynchronous = True

    @property
    @memoized
    def case_es(self):
        return CaseES(self.domain)


    def build_query(self, case_type=None, filter=None, status=None, owner_ids=None, search_string=None):
        # there's no point doing filters that are like owner_id:(x1 OR x2 OR ... OR x612)
        # so past a certain number just exclude
        owner_ids = owner_ids or []
        MAX_IDS = 50

        def _filter_gen(key, flist):
            if flist and len(flist) < MAX_IDS:
                yield {"terms": {
                    key: [item.lower() if item else "" for item in flist]
                }}

            # demo user hack
            elif flist and "demo_user" not in flist:
                yield {"not": {"term": {key: "demo_user"}}}

        def _domain_term():
            return {"term": {"domain.exact": self.domain}}

        subterms = [_domain_term(), filter] if filter else [_domain_term()]
        if case_type:
            subterms.append({"term": {"type.exact": case_type}})

        if status:
            subterms.append({"term": {"closed": (status == 'closed')}})

        user_filters = list(_filter_gen('owner_id', owner_ids))
        if user_filters:
            subterms.append({'or': user_filters})

        if search_string:
            query_block = {
                "query_string": {"query": search_string}}  # todo, make sure this doesn't suck
        else:
            query_block = {"match_all": {}}

        and_block = {'and': subterms} if subterms else {}

        es_query = {
            'query': {
                'filtered': {
                    'query': query_block,
                    'filter': and_block
                }
            },
            'sort': self.get_sorting_block(),
            'from': self.pagination.start,
            'size': self.pagination.count,
        }

        return es_query

    @property
    @memoized
    def es_results(self):
        case_es = self.case_es
        query = self.build_query(case_type=self.case_type, filter=self.case_filter,
                                 status=self.case_status, owner_ids=self.case_owners,
                                 search_string=SearchFilter.get_value(self.request, self.domain))
        return case_es.run_query(query)

    @property
    @memoized
    def case_owners(self):
        if self.individual:
            group_owners = self.case_sharing_groups
        else:
            group_owners = Group.get_case_sharing_groups(self.domain)
        group_owners = [group._id for group in group_owners]
        return [user.get('user_id') for user in self.users] + group_owners

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
        if '_source' in row:
            case_dict = row['_source']
        else:
            raise ValueError("Case object is not in search result %s" % row)

        if case_dict['domain'] != self.domain:
            raise Exception("case.domain != self.domain; %r and %r, respectively" % (case_dict['domain'], self.domain))

        return case_dict

    @property
    def shared_pagination_GET_params(self):
        shared_params = super(CaseListMixin, self).shared_pagination_GET_params
        shared_params.append(dict(
            name=SelectOpenCloseFilter.slug,
            value=self.request.GET.get(SelectOpenCloseFilter.slug, '')
        ))
        return shared_params


class CaseListReport(CaseListMixin, ProjectInspectionReport):
    name = ugettext_noop('Case List')
    slug = 'case_list'

    @property
    def user_filter(self):
        return super(CaseListReport, self).user_filter

    @property
    @memoized
    def rendered_report_title(self):
        if not self.individual:
            self.name = _("%(report_name)s for %(worker_type)s") % {
                "report_name": _(self.name),
                "worker_type": _(SelectMobileWorkerFilter.get_default_text(self.user_filter))
            }
        return self.name

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(_("Case Type"), prop_name="type.exact"),
            DataTablesColumn(_("Name"), prop_name="name.exact"),
            DataTablesColumn(_("Owner"), prop_name="owner_display", sortable=False),
            DataTablesColumn(_("Created Date"), prop_name="opened_on"),
            DataTablesColumn(_("Created By"), prop_name="opened_by_display", sortable=False),
            DataTablesColumn(_("Modified Date"), prop_name="modified_on"),
            DataTablesColumn(_("Status"), prop_name="get_status_display", sortable=False)
        )
        return headers

    @property
    def rows(self):
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
            return [_format_row(item) for item in self.es_results['hits'].get('hits', [])]
        except RequestFailed:
            pass

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

    name = ugettext_noop("Maps Sandbox")
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
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return cls.get_config(domain)
