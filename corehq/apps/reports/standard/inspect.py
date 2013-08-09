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
import logging

from casexml.apps.case.models import CommCareCaseAction
from corehq.apps.api.es import CaseES
from corehq.apps.hqsofabed.models import HQFormData
from corehq.apps.reports.filters.search import SearchFilter
from corehq.apps.reports.models import HQUserType
from corehq.apps.reports.standard import ProjectReport, ProjectReportParametersMixin, DatespanMixin
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.display import xmlns_to_name
from corehq.apps.reports.fields import SelectOpenCloseField, SelectMobileWorkerField, StrongFilterUsersField
from corehq.apps.reports.generic import GenericTabularReport, ProjectInspectionReportParamsMixin, ElasticProjectInspectionReport
from corehq.apps.reports.standard.monitoring import MultiFormDrilldownMixin
from corehq.apps.reports.util import datespan_from_beginning
from corehq.apps.users.models import CommCareUser, CouchUser
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX
from dimagi.utils.couch import get_cached_property, IncompatibleDocument
from dimagi.utils.couch.database import get_db
from dimagi.utils.couch.pagination import CouchFilter
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.timezones import utils as tz_utils
from corehq.apps.groups.models import Group
from corehq.apps.reports.graph_models import PieChart, MultiBarChart, Axis
import rawes
from corehq import elastic

class ProjectInspectionReport(ProjectInspectionReportParamsMixin, GenericTabularReport, ProjectReport, ProjectReportParametersMixin):
    """
        Base class for this reporting section
    """
    exportable = False
    asynchronous = False
    ajax_pagination = True
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.SelectMobileWorkerField']


class SubmitHistory(ElasticProjectInspectionReport, ProjectReport, ProjectReportParametersMixin, MultiFormDrilldownMixin, DatespanMixin):
    name = ugettext_noop('Submit History')
    slug = 'submit_history'
    fields = [
              'corehq.apps.reports.fields.CombinedSelectUsersField',
              'corehq.apps.reports.filters.forms.FormsByApplicationFilter',
              'corehq.apps.reports.fields.DatespanField']
    ajax_pagination = True
    filter_users_field_class = StrongFilterUsersField
    include_inactive = True


    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn(_("View Form")),
            DataTablesColumn(_("Username"), prop_name="form.meta.username"),
            DataTablesColumn(_("Submit Time"), prop_name="form.meta.timeEnd"),
            DataTablesColumn(_("Form"), prop_name="form.@name"))
        return headers

    @property
    def default_datespan(self):
        return datespan_from_beginning(self.domain, self.datespan_default_days, self.timezone)

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
                            "to": self.datespan.enddate_param,
                            "include_upper": False}}},
                "filter": {"and": []}}

            xmlnss = filter(None, [f["xmlns"] for f in self.all_relevant_forms.values()])
            if xmlnss:
                q["filter"]["and"].append({"terms": {"xmlns.exact": xmlnss}})

            def any_in(a, b):
                return any(i in b for i in a)

            if self.request.GET.get('all_mws', 'off') != 'on' or any_in(
                    [str(HQUserType.DEMO_USER), str(HQUserType.ADMIN), str(HQUserType.UNKNOWN)],
                    self.request.GET.getlist('ufilter')):
                q["filter"]["and"].append(
                    {"terms": {"form.meta.userID": filter(None, self.combined_user_ids)}})
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
            except (ResourceNotFound, IncompatibleDocument):
                name = "<b>[unregistered]</b>"

            yield [
                form_data_link(form["_id"]),
                (username or _('No data for username')) + (" %s" % name if name else ""),
                datetime.strptime(form["form"]["meta"]["timeEnd"], '%Y-%m-%dT%H:%M:%SZ').strftime("%Y-%m-%d %H:%M:%S"),
                xmlns_to_name(self.domain, form.get("xmlns"), app_id=form.get("app_id")),
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
        if self.owner_id:
            try:
                doc = get_db().get(self.owner_id)
            except ResourceNotFound:
                pass
            else:
                return {
                    'CommCareUser': CommCareUser,
                    'Group': Group,
                }.get(doc['doc_type']), doc
        return None, None

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
        'corehq.apps.reports.fields.FilterUsersField',
        'corehq.apps.reports.fields.SelectCaseOwnerField',
        'corehq.apps.reports.fields.CaseTypeField',
        'corehq.apps.reports.fields.SelectOpenCloseField',
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
        query_results = case_es.run_query(query)

        if query_results is None or 'hits' not in query_results:
            logging.error("CaseListMixin query error: %s, urlpath: %s, params: %s, user: %s yielded a result indicating a query error: %s, results: %s" % (
                self.__class__.__name__,
                self.request.path,
                self.request.GET.urlencode(),
                self.request.couch_user.username,
                simplejson.dumps(query),
                simplejson.dumps(query_results)
            ))
        return query_results

    @property
    @memoized
    def case_owners(self):
        if self.individual:
            group_owners_raw = self.case_sharing_groups
        else:
            group_owners_raw = Group.get_case_sharing_groups(self.domain)
        group_owners = [group._id for group in group_owners_raw]
        ret = [user.get('user_id') for user in self.users]
        if len(self.request.GET.getlist('ufilter')) == 1 and str(HQUserType.UNKNOWN) in self.request.GET.getlist('ufilter'):
            #not applying group filter
            pass
        else:
            ret += group_owners
        return ret

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
    @memoized
    def rendered_report_title(self):
        if not self.individual:
            self.name = _("%(report_name)s for %(worker_type)s") % {
                "report_name": _(self.name),
                "worker_type": _(SelectMobileWorkerField.get_default_text(self.user_filter))
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
            #should this fail due to es_results being None or having no 'hits',
            #return None, which will fail when trying to render rows, to return an error back to the datatables
            return [_format_row(item) for item in self.es_results['hits'].get('hits', [])]
        except RequestFailed:
            pass

    def date_to_json(self, date):
        return tz_utils.adjust_datetime_to_timezone\
            (date, pytz.utc.zone, self.timezone.zone).strftime\
            ('%Y-%m-%d %H:%M:%S') if date else ""

class GenericPieChartReportTemplate(ProjectReport, GenericTabularReport):
    """this is a report TEMPLATE to conduct analytics on an arbitrary case property
    or form question. all values for the property/question from cases/forms matching
    the filters are tabulated and displayed as a pie chart. values are compared via
    string comparison only.

    this report class is a TEMPLATE -- it must be subclassed and configured with the
    actual case/form info to be useful. coming up with a better way to configure this
    is a work in progress. for now this report is effectively de-activated, with no
    way to reach it from production HQ.

    see the reports app readme for a configuration example
    """

    name = ugettext_noop('Generic Pie Chart (sandbox)')
    slug = 'generic_pie'
    fields = ['corehq.apps.reports.fields.DatespanField',
              'corehq.apps.reports.fields.AsyncLocationField']
    # define in subclass
    #mode = 'case' or 'form'
    #submission_type = <case type> or <xform xmlns>
    #field = <case property> or <path to form instance node>

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return True

    @property
    def headers(self):
        return DataTablesHeader(*(DataTablesColumn(text) for text in [
                    _('Response'), _('# Responses'), _('% of responses'),
                ]))

    def _es_query(self):
        es_config_case = {
            'index': 'full_cases',
            'type': 'full_case',
            'field_to_path': lambda f: '%s.#value' % f,
            'fields': {
                'date': 'server_modified_on',
                'submission_type': 'type',
            }
        }
        es_config_form = {
            'index': 'full_xforms',
            'type': 'full_xform',
            'field_to_path': lambda f: 'form.%s.#value' % f,
            'fields': {
                'date': 'received_on',
                'submission_type': 'xmlns',
            }
        }
        es_config = {
            'case': es_config_case,
            'form': es_config_form,
        }[self.mode]

        MAX_DISTINCT_VALUES = 50

        es = elastic.get_es()
        filter_criteria = [
            {"term": {"domain": self.domain}},
            {"term": {es_config['fields']['submission_type']: self.submission_type}},
            {"range": {es_config['fields']['date']: {
                    "from": self.start_date,
                    "to": self.end_date,
                }}},
        ]
        if self.location_id:
            filter_criteria.append({"term": {"location_": self.location_id}})
        result = es.get('%s/_search' % es_config['index'], data={
                "query": {"match_all": {}}, 
                "size": 0, # no hits; only aggregated data
                "facets": {
                    "blah": {
                        "terms": {
                            "field": "%s.%s" % (es_config['type'], es_config['field_to_path'](self.field)),
                            "size": MAX_DISTINCT_VALUES
                        },
                        "facet_filter": {
                            "and": filter_criteria
                        }
                    }
                },
            })
        result = result['facets']['blah']

        raw = dict((k['term'], k['count']) for k in result['terms'])
        if result['other']:
            raw[_('Other')] = result['other']
        return raw

    def _data(self):
        raw = self._es_query()
        return sorted(raw.iteritems())

    @property
    def rows(self):
        data = self._data()
        total = sum(v for k, v in data)
        def row(k, v):
            pct = v / float(total) if total > 0 else None
            fmtpct = ('%.1f%%' % (100. * pct)) if pct is not None else u'\u2014'
            return (k, v, fmtpct)
        return [row(*r) for r in data]

    def _chart_data(self):
        return {
                'key': _('Tallied by Response'),
                'values': [{'label': k, 'value': v} for k, v in self._data()],
        }

    @property
    def location_id(self):
        return self.request.GET.get('location_id')

    @property
    def start_date(self):
        return self.request.GET.get('startdate')

    @property
    def end_date(self):
        return self.request.GET.get('enddate')

    @property
    def charts(self):
        if 'location_id' in self.request.GET: # hack: only get data if we're loading an actual report
            return [PieChart(None, **self._chart_data())]
        return []



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
