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
import re
import os.path

from casexml.apps.case.models import CommCareCaseAction
from corehq.apps.api.es import CaseES
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
from dimagi.utils.modules import to_function
from corehq.apps.groups.models import Group
from corehq.apps.reports.graph_models import PieChart, MultiBarChart, Axis
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
                if username not in ['demo_user', 'admin']:
                    full_name = get_cached_property(CouchUser, uid, 'full_name', expiry=7*24*60*60)
                    name = '"%s"' % full_name if full_name else ""
                else:
                    name = ""
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
            'index': 'report_cases',
            'type': 'report_case',
            'field_to_path': lambda f: '%s.#value' % f,
            'fields': {
                'date': 'server_modified_on',
                'submission_type': 'type',
            }
        }
        es_config_form = {
            'index': 'report_xforms',
            'type': 'report_xform',
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



class GenericMapReport(ProjectReport, ProjectReportParametersMixin):
    """instances must set:

    data_source -- config about backend data source
    display_config -- configure the front-end display of data

    data_source: {
      'adapter': type of data source ('test', 'report', etc.),
      'geo_column': column in returned data identifying the geo point (defaults to "geo"),
      <custom parameters by adapter>

      adapter == 'report'
      'report': 'fully qualified name of ReportDataSource class'
      'report_params': optional dict of (static) config parameters for ReportDataSource
    }

    display_config: {
      'name_column': column data used in the header of the detail popup,
      'column_titles': {'column name': 'display title for column},
      'detail_columns': [list of column data to display in detail popup],
      'enum_captions': {
        'col with enum values': {'enum value': 'enum caption'}
      },
      'numeric_format': {
        'numeric column': 'body of javascript function that formats the number appropriately (variable is 'x')'
      },
      'metrics': [ <toggleable data display modes> (may be omitted during report prototyping)
        one or more of:
        {
          'title': display title,
          'size': [optional] controls the size of the marker-- radius in pixels OR
            {
              'column': column containing the relevant variable,
              'baseline': value corresponding to a marker of radius 10 pixels,
              'min': minimum marker radius (pixels) [optional],
              'max': maximum marker radius (pixels) [optional],
            },
          'color': [optional] controls the color of the marker-- a css color value OR
            {
              'column': column containing the relevant variable,
              one of either 'categories' or 'colorstops'
              'categories': {'enum value': css color},
                 - special value '_other' can act as catch-all for values not explicitly listed
                 - special value '_null' will be used for rows where the value is blank; if absent, such rows will be hidden
              'colorstops': (to create sliding color scales) [list of colorstops: [value, csscolor]],
              'thresholds': [optional] [list of numerical threshold values to convert numeric data into enum 'buckets'],
            },
          'icon': [optional] use an icon as the marker; overrides size/color-- an image url OR
            {
              'column': column containing the relevant variable,
              'categories': as in 'color', only a url instead of a color
              'thresholds': as in 'color'
            },
        }
      ]
    }
    """

    report_partial_path = "reports/partials/maps.html"
    flush_layout = True
    asynchronous = False  # TODO: we want to support async load

    def _get_data(self):
        adapter = self.data_source['adapter']
        geo_col = self.data_source.get('geo_column', 'geo')

        try:
            loader = getattr(self, '_get_data_%s' % adapter)
        except AttributeError:
            raise RuntimeError('unknown adapter [%s]' % adapter)
        data = loader(self.data_source, dict(self.request.GET.iteritems()))

        # debug
        #import pprint
        #data = list(data)
        #pprint.pprint(data)

        return self._to_geojson(data, geo_col)

    def _to_geojson(self, data, geo_col):
        def _parse_geopoint(raw):
            latlon = [float(k) for k in re.split(' *,? *', raw)[:2]]
            return [latlon[1], latlon[0]] # geojson is lon, lat

        def points():
            for row in data:
                geo = row[geo_col]
                if geo is None:
                    continue

                e = geo
                depth = 0
                while hasattr(e, '__iter__'):
                    e = e[0]
                    depth += 1

                if depth < 2:
                    if depth == 0:
                        geo = _parse_geopoint(geo)
                    feature_type = 'Point'
                else:
                    if depth == 2:
                        geo = [geo]
                        depth += 1
                    feature_type = 'MultiPolygon' if depth == 4 else 'Polygon'

                yield {
                    'type': 'Feature',
                    'geometry': {
                        'type': feature_type,
                        'coordinates': geo,
                    },
                    'properties': dict((k, v) for k, v in row.iteritems() if k != geo_col),
                }

        return {
            'type': 'FeatureCollection',
            'features': list(points()),
        }

    def _get_data_report(self, params, filters):
        # this ordering is important!
        # in the reverse order you could view a different domain's data just by setting the url param!
        config = dict(filters)
        config.update(params.get('report_params', {}))
        config['domain'] = self.domain

        DataSource = to_function(params['report'])
        return DataSource(config).get_data()

    def _get_data_csv(self, params, filters):
        import csv
        with open(params['path']) as f:
            return list(csv.DictReader(f))

    def _get_data_geojson(self, params, filters):
        with open(params['path']) as f:
            data = json.load(f)

        for feature in data['features']:
            item = dict(feature['properties'])
            item['geo'] = feature['geometry']['coordinates']
            yield item

    @property
    def report_context(self):
        context = {
            'data': self._get_data(),
            'config': self.display_config,
        }

        return dict(
            context=context,
        )

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return True









class DemoMapReport(GenericMapReport):
    """this report is a demonstration of the maps report's capabilities
    it uses a static dataset
    """

    name = ugettext_noop("Maps: Highest Mountains")
    slug = "maps_demo"
    data_source = {
        "adapter": "csv",
        "geo_column": "geo",
        "path": os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tests/maps_demo/mountains.csv'),
    }
    display_config = {
        "name_column": "name",
        "detail_columns": [
            "rank",
            "height",
            "prominence",
            "country",
            "range",
            "first_ascent",
            "num_ascents",
            "num_deaths",
            "death_rate"
        ],
        "column_titles": {
            "country": "Country",
            "height": "Elevation",
            "prominence": "Topographic Prominence",
            "range": "Range",
            "first_ascent": "First Ascent",
            "rank": "Ranking",
            "num_ascents": "# Ascents",
            "num_deaths": "# Deaths",
            "death_rate": "Death Rate"
        },
        "enum_captions": {
            "first_ascent": {
                "_null": "Unclimbed"
            },
            "rank": {
                "-": "Top 10"
            }
        },
        "numeric_format": {
            "rank": "return '#' + x",
            "height": "return x + ' m | ' + Math.round(x / .3048) + ' ft'",
            "prominence": "return x + ' m | ' + Math.round(x / .3048) + ' ft'",
            "death_rate": "return (100. * x).toFixed(2) + '%'"
        },
        "metrics": [
            {
                "color": {
                    "column": "rank",
                    "thresholds": [
                        11,
                        25,
                        50
                    ]
                }
            },
            {
                "color": {
                    "column": "height",
                    "colorstops": [
                        [
                            7200,
                            "rgba(20,20,20,.8)"
                        ],
                        [
                            8848,
                            "rgba(255,120,20,.8)"
                        ]
                    ]
                }
            },
            {
                "size": {
                    "column": "prominence"
                },
                "color": {
                    "column": "prominence",
                    "thresholds": [
                        1500,
                        3000,
                        4000
                    ],
                    "categories": {
                        "1500": "rgba(255, 255, 60, .8)",
                        "3000": "rgba(255, 128, 0, .8)",
                        "4000": "rgba(255, 0, 0, .8)",
                        "-": "rgba(150, 150, 150, .8)"
                    }
                }
            },
            {
                "icon": {
                    "column": "country",
                    "categories": {
                        "Pakistan": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAPCAIAAACAzcMBAAAABmJLR0QA/wD/AP+gvaeTAAAAw0lEQVQ4y2P4jwr2nz/G6ChDKmIYUqZIBhvGtRewuyoiCcqSZopylNXhyyc53JTgIlHN2UZpHqSZsuPUgcpZ7XCuXV7Qm4/vyma0kGCKVIjRv3//oltykDWE1KdJhxiTYIpphhdQpHpOJ0WhC3HL7Sf3Od2V0bQxO8mRFi5AwfWHd/B7a8AFgYZ6lMWQFkdP37wAir98/7pz+bSKWW1dK6av2L8ROdaITS+T1s178vr5n79/rty/WTq9GTXtDL0cQAwCAFS5mrmuqFgRAAAAAElFTkSuQmCC",
                        "China/Pakistan": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAPCAYAAAAPr1RWAAAAAXNSR0IArs4c6QAAAAZiS0dEAP8A/wD/oL2nkwAAAAlwSFlzAAALEwAACxMBAJqcGAAAAAd0SU1FB90IHwcYMYz0J78AAAFiSURBVDjLY3g/tfM/Oj5Xm/M/z1Tsf565GIQmEzMgG/phbgeK4eVpQv/zralk+PfDrf8/LW2HG54PdHm+jdj/Ii8R8g3/MLvj/8/zLf//v2/8//914/+rCzPhCgqAhhf7QQyvslP8PzfS8X+huSSaQeL4Xf5pSfv/Pw+a/v++1YwIc5gFtmL/651U/1+oz/tfZIFq8Oxwu//tHjr4Df+4CBjeMyD0+QaE4YWuov9LI4X/n67K/L86yQdFc6+P4f+nfQ3/VyZ6Ew5z9NRSFg+J0Gp7xf/vpnb8nxNuj2HAjFAboLwS6YYXOIqC6U5PXbD4mmRf8lMLRjqHYpjL73RUAsNcCqtB+Wbi5BkOwqAwB8kdK0/9X2olgyIHsnBSgBn5hoNSy6OeWrD8k976/5szQ/6vAkbwFiB9uDQRIxWRZDgsne/Iifj/sLv2/9sp7f9vtpYBU4oXlnRPhuEUZf8hZTgA8YnkUuk5wigAAAAASUVORK5CYII=",
                        "Bhutan/China": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAPCAYAAAAPr1RWAAAABmJLR0QA/wD/AP+gvaeTAAAB5UlEQVQ4y63Q20uTARzGcf+ctTWsiAbFmstRGXXRwYIgKqGRwaib6krwKhdkB6I1h+AsOhlkrHVYh2lTslndaLVDc+/51Ls5urK7bxeBIFrtDS+eu9/z4eHX0kh5We3U73vRu9bQsmpgqpVGysv3Pg/Kdhey3+Uc10d9VF+F0XJnsZ8FfsNP1mM/3ot21I3sdy3GEW6n/Rj5PrTPaUy1yo9GDaE0jZW7hRyL8m335v/H65kQczNv0OQKplKkZhmIDxOIQzeQ9geXwI5x62k7+tcMlmUhvBhk7kCQQvwacjKGeOY4YsDjHLdyEex8D+Z4GG20C70wi5B/h/llFvHta+ofp1CvX3S+XMtHma+ZGMIMUqWI9X4CtVxGmZpEOt+N2OFbtrgp3EpvxSxlKb28jHKqA6X3HFKsH+HDNFK0B9nvQmxvXRH+J25nwwjlAuLIbbQ7g0g7NyHu2UIpfgX90V2se0OoyTjVZvFaaiNm9hjaRILyWIbi8ADV4QGkxFWUg6ElZT15k58LC0i7fE3g6Q3Y4xFqpU8IqRHUyBGkE50Iz9Mo4UPLykpoHcK+tubeYsS3YVw4jRT0Lh5Uwp2Yk2NUug//EfkrPv/Ai3HSveKB1ObBvNSLHHA7x+3+tag7XI6LzeQXCpSkKvvyoHIAAAAASUVORK5CYII=",
                        "China/India": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAPCAYAAAAPr1RWAAAAAXNSR0IArs4c6QAAAAZiS0dEAP8A/wD/oL2nkwAAAAlwSFlzAAALEwAACxMBAJqcGAAAAAd0SU1FB90IHwcUGGLz8N8AAADoSURBVDjLY3ifpPQfJ07GI0cEZkDmfMhURJH8MVn2/4d0ReoY/n2C3P9PhQooLv+Qofj/c5kC+YaDXPdztuz//7ul/v/fIfX/a5s8im8+VytQ5vJPBQr//6yR/v97uQyGIvTgIt7wqZ3/Qfjjoo7/72dA6Zkd/2Hin5a2//+6s+3/leqa/3uSisA0TI4QZsAn+X1/6/8Pszv+X6qo/n+mqPL/qYKK/6eB9KXKasoN/7gQ4oOdCYVgg5d4Z4LpnfGFlBsOwyCXnoa5vLCCOi5HxqCw3g0M86vVtcSHeXkk939a4VHD6W84AMcMSEsYuXzSAAAAAElFTkSuQmCC",
                        "India/Nepal": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAPCAYAAAAPr1RWAAAAAXNSR0IArs4c6QAAAAZiS0dEAP8A/wD/oL2nkwAAAAlwSFlzAAALEwAACxMBAJqcGAAAAAd0SU1FB90IHwcVISTtSZYAAAHKSURBVDjLrZDRS5NRGId3111Q/4H3GULpkopUUihoKgjbhcoCY9GNIZP2OflK55wOdblE3EWtGmWCxpTpZwgqJTnTIFQUJQmT2EVOcSip0J7mAWOsVX6yFx5e3pfD8zvnaPCcI55eSzGRDi2J++OgSVwEjDpGjdeYri8g2pViuWK8QViv5avhIq9NRay1XU69/JCPpVcZla6z33k+9fIDQoZs+isKWXLmqpQnlPIowMZDH5GeYX5Mz7PlGxDz3F03z0rduNvHiOzscZRKKt8eec/+ypqYdxdWWOgc4IOpjeCtVoImF4+lbqZmvxGNRtXLN1zP2Vv6ws+tbXY/LTKsdwixL0cWXSlp5HPrC/p8E4TWd9TJw84ngnWnF3/HEM0NQzjuD2KXA7EewNWk4H81ib8nyEtlkeXVTfXycIuX77GAXu844+9W8XhmmZkJcdTSnG46QTxX9FlU69KolfKRHUVY7+Vhjs1nyrI5ZTtJ4vl/kVRuNefQ4K/C8bYOW/cdpNtZIiBdZcCfcoMW2a4T4gMax2RqrQXiNeZCdQFJb15TeYm6pxXY30g88JQjmTKFXG3AX//ccjMDa3UuFmPGb3F8wNmyC/8N+AVYXqHDIJue6wAAAABJRU5ErkJggg==",
                        "Nepal": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA4AAAARCAYAAADtyJ2fAAAABmJLR0QA/wD/AP+gvaeTAAABnElEQVQoz2NgMe9fzWA9WYqBVJCpnvW/WjXpt4RpVwkDQwMT0Rrz1DL+3xGx+X9M3OWft3bJcwbzSRYkaYThmXLhf3SMGucx6HVzk6QRhC+IOf6L1Cz4yGA5xQevxnsKbv+fBhX8/zB95f/HrilgPsiAlTKBf0wM6w9iDTyQxldlPf+/7j7+HwQ+rdv9/0VaA9z2GyJ2/wvV0n7ymvUWoQQe2EY5l/9fNh/4//vJy/8fF2z4f1fCHsP5O6W8/rvoVDxgsJpqgOHHWyK2/xM1cv5b6tU8dNSrvIKO7fWqLrOZT9zJYD7FCzVwxO2ATrP976lT9prBcro0UaH6Mrv1/9v2OWD/3QRq9tEpfYtXM0jji4Tq/79uPQQHzvcTF/8/8cwAa/bXxqM5Xz3z/9vmGf9h4N+Pn/9f5rVD/CwK0lyCXTPIxmdhxf+/7Dr6/8+b9/8/rd75/4l7GiLAcGmG+fGRVfT/F0m1/x9aRmNEBUhzgHYxqmZsSQ4bvgnUHKhV9JrBfII4WKOxQf3/dGDWIgbHa+b9ZzObcAOkGQDaD1JZd6jOSgAAAABJRU5ErkJggg==",
                        "India": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAPCAYAAAAPr1RWAAAABmJLR0QA/wD/AP+gvaeTAAAAdElEQVQ4y2P4P9P4P60ww6jhA2A4keD06Wf/Z826BKaJBUQZfuzY4/+7dt3/v23b3f87d97/f/z4E+oZPnXqebDBOTn7wfSUKeepZzjIpSAXb9t27/+OHfeo63JYmM+ceen/mTPPiQ9zoQ72/7TCo4bT33AAzkG28NnasBMAAAAASUVORK5CYII=",
                        "China/Nepal": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAPCAYAAAAPr1RWAAAAAXNSR0IArs4c6QAAAAZiS0dEAP8A/wD/oL2nkwAAAAlwSFlzAAALEwAACxMBAJqcGAAAAAd0SU1FB90IHwcYDjqSCoIAAAG4SURBVDjLY7inKfAfGU/Ts/p/WUscwtdBlSMVMyBzHlrw/1+iYfN/nbrF/0062v/fd7P/f2DCTx3D37dx/F9lbvX/rrza/0sKWv/n6tj+P24m+/9ZMA/5hoNc93ke2///9xj+b28w+f/ERRlsAQjv0zb6v87f4P8tTSHyXf7Enff/zwPM/zfnmcINhuGb6hr/F2ja/t+rrUKe4Y+d+f7f1xP4v9LE6v99Da3/D23t/z+PjwFaavH/qacG2JIjygb/5+tYIiKclDAH4eUa1v+f+Pv+f1mY9f/bvqb/LwtS/j92d4f74ra8+v+VGpb/NwAj/C45ht9T0fr/Mjf9/7uJVf+fp8T/v6eojhFUZ5R0/8/Wsv1/UluWNMNhBtwBYlBYT9O2/z9X2xornqhnB4x0ZdINv6ugDgwGtf+ztOyIDmeiDH/s5fX/aXgoOLxBPphNhgVYDX/s4vr/TUP5/3eT2/6/qsj//9DSGmzBHBItwGK4zf+nocFgg8G4v/n/Y29veByQYgFWlz+ydwQmxcz/bzvr/r/ITAGWOVYokUysBTjD/IGh6f/Hrm7/7xti5liQBXOByZCQBQC9TOVO1zHzuwAAAABJRU5ErkJggg==",
                        "China/Kyrgyzstan": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAOCAYAAADE84fzAAAABmJLR0QA/wD/AP+gvaeTAAABFUlEQVQ4y82UsUoDQRCGv9m9XG4PQgjaiCSlwUJtrC31lXxJtRAjKChBi1glXtSce7c7FnkAj5wB/2aa4YP5Z/6R2eBI2ZIMW1RzuABW17WhkkZN4xK77zE7AYDqLqOeuPbwzvGK9GxJ52SFrgScYkbfGKf4q3xzuPQi6eknyUFJfZ9BHuDLkgw9elhSPXXRud3Mc7NbYUeeOE8w/YCfOMgjcWGx4xJJY4uFVoJ6IX5YwsLSv5xBKWiRIEEwvRbwuLSEaRe75wnPKdWto3rMMENPeO0Q3pLNPdd3i79xyCDQPS/QwpJdFNQPGf46R5e23bXUEwdRCC8pgqJBCNP1FL9Go3H8DWAUFAjydyFaLwCI8n9+yw+uh21xPR0lJAAAAABJRU5ErkJggg==",
                        "China": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAPCAIAAACAzcMBAAAABmJLR0QA/wD/AP+gvaeTAAAAjUlEQVQ4y2O4pymABekIYBfHgRjgrIcW/HD2hx72Byb85Jjyvo3jiQcvhH1fR+CBGf+zYB4STAFa+3ke2/97DP+uM74u4oI6zZz/eQwPaW554s778wDz960syHLIfiTKlMfOfPf1BB458d03gOp84skLdxcJ4YKM3tVxkBm6yOiRAx+ZMU0JGjVl8JsCABF+frZhYhUiAAAAAElFTkSuQmCC",
                        "China/India/Nepal": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAPCAYAAAAPr1RWAAAAAXNSR0IArs4c6QAAAAZiS0dEAP8A/wD/oL2nkwAAAAlwSFlzAAALEwAACxMBAJqcGAAAAAd0SU1FB90IHwcVCRFY4WwAAAH0SURBVDjLrZJPTxNRFMV/bzptp50ptilCaQsIQSVGcaFLEz+HWzd+BL+eKxdiXFDEuJEAIqX/S9vpMDPvXRdKLAH/DPHs3rvJOfeec1T/5bowg21/iUe5No6KQQGXpslgzT5UVnB84aBbYv+8iPM4QqXl/5Bn72tSecNaOKbci3j7ZoWedrDnzY3IbQCVFnJPYzJ3NLlpjP3Z4DThoT+gZfJ0HJc1GWArk3xziRTnH1PooUKPLeLmr4MWgoDaQcBuf5Fm7CXc/MkrAKQgjDqKUI9hc0Jq7hapShnTP8FmQqXhs99V7C4v8OyBh5NK4LkZKdBgAoVdq5DeWMZ9XsWur9DpFghDQzWj2Wg12X7f5suZQiRBoBeID5ugDeFRhASazt4RInBy4qNEKDfbFI9bfDiMGIbqz4FeZdcE7xoI8Clb5LhWQ8UGKQg9IF22CD0XC9jrK9bnYDEn/0h+0XtLsXk+QJfmKaVDeqcTqksu1epssL9vkHr9wr0kqfur3A3PsJcrWHkHM/aJjlvs5IrkCl+xVZSs51c+l26TubeK5eXR3SEyDdjqDdihnkjgmkAVlpfH8vIApEoFlOeigK3pgOmoTizpm5ILejgiPu0iYUT0rY2MJj9lkwlca4tu9ZBpgFVwMWcTzNifueuHQIM6zl8s+g5AOt+1kjl9KgAAAABJRU5ErkJggg==",
                        "Afghanistan/Pakistan": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAPCAYAAAAPr1RWAAAABmJLR0QA/wD/AP+gvaeTAAAA50lEQVQ4y2NgYGD4jws7A/F+PNg5GahuJh48ajjZhh9gZf1/Sk/v/xlz8/+n9PX/H5WSoo7hR2Ul/p/2sPl/WFzo/+XgwP+HJUX+n3ex/n9YXpJyw8952/4/Zarz/2KA+/+Hc3r/X/Rz+3/SXPf/OU9ryg2/mhL0/0p67P9Lcf7/zwc4/T8f7g7mX00Jptzwi+Fe/8+62fy/lh3//97kxv+XYoP/n3W3/X8+wodyw4/pqv+/Upj4/6wH0NXu7v/PejoD+Qn/j+qqUSe1HFGV+f9iycL/T+fN+v9ixdL/R5SlRzPRIDUcAOepDzYPRuOVAAAAAElFTkSuQmCC",
                        "Tajikistan": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAMCAYAAACJOyb4AAAABmJLR0QA/wD/AP+gvaeTAAAAkElEQVQ4y2M4w8Dwn1aYYega/nrmzP/E4jezp/wnRT3Df6LAv///vlz4/+/7bTAN4hMDiDIcYuD//39fzEXhU274v9///329DKR//f/zdjOYhvB/U8nl3278/wN09e+Xi/7/eTkHzCfK5TMPzfxPCM8+NPX/+sMl/5ccavu/4VAJmE+MPgaGNGCSoRUesoYDAFwH0YKibe8HAAAAAElFTkSuQmCC"
                    }
                }
            },
            {
                "color": {
                    "column": "range"
                }
            },
            {
                "color": {
                    "column": "first_ascent",
                    "thresholds": [
                        1940,
                        1955,
                        1970,
                        1985,
                        2000
                    ],
                    "categories": {
                        "1940": "rgba(38, 75, 89, .8)",
                        "1955": "rgba(36, 114, 117, .8)",
                        "1970": "rgba(50, 153, 132, .8)",
                        "1985": "rgba(95, 193, 136, .8)",
                        "2000": "rgba(159, 230, 130, .8)",
                        "-": "rgba(33, 41, 54, .8)",
                        "_null": "rgba(255, 255, 0, .8)"
                    }
                }
            },
            {
                "size": {
                    "column": "num_ascents",
                    "baseline": 100
                }
            },
            {
                "size": {
                    "column": "num_deaths",
                    "baseline": 100
                }
            },
            {
                "color": {
                    "column": "death_rate",
                    "colorstops": [
                        [
                            0,
                            "rgba(20,20,20,.8)"
                        ],
                        [
                            0.4,
                            "rgba(255,0,0,.8)"
                        ]
                    ]
                }
            },
            {
                "title": "Ascents vs. Death Rate",
                "size": {
                    "column": "num_ascents",
                    "baseline": 200
                },
                "color": {
                    "column": "death_rate",
                    "colorstops": [
                        [
                            0,
                            "rgba(20,20,20,.8)"
                        ],
                        [
                            0.4,
                            "rgba(255,0,0,.8)"
                        ]
                    ]
                }
            }
        ]
    }

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return user and user.is_previewer()

class DemoMapReport2(GenericMapReport):
    """this report is a demonstration of the maps report's capabilities
    it uses a static dataset
    """

    name = ugettext_noop("Maps: States of India")
    slug = "maps_demo2"
    data_source = {
        "adapter": "geojson",
        "geo_column": "geo",
        "path": os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tests/maps_demo/india.geojson'),
    }
    display_config = {
        'name_column': 'name',
        'detail_columns': ['iso', 'type', 'pop', 'area', 'pop_dens', 'lang', 'literacy', 'urbanity', 'sex_ratio'],
        'column_titles': {
            'iso': 'ISO 3166-2',
            'type': 'Type',
            'pop': 'Population',
            'area': 'Area',
            'pop_dens': 'Population Density',
            'lang': 'Primary Official Language',
            'literacy': 'Literacy Rate',
            'urbanity': '% Urban',
            'sex_ratio': 'Sex Ratio',
        },
        'numeric_format': {
            'iso': "return 'IN-' + x",
            'area': "return x + ' km^2'",
            'pop': "return x.toString().replace(/\B(?=(?:\d{3})+(?!\d))/g, ',')",
            'pop_dens': "return x + ' /km^2'",
            'literacy': "return x + '%'",
            'urbanity': "return x + '%'",
            'sex_ratio': "return x/1000. + ' females per male'",
        },
        'metrics': [
            {'color': {'column': 'pop'}},
            {'color': {'column': 'pop_dens',
                       'colorstops': [
                        [0, 'rgba(20, 20, 20, .8)'],
                        [1200, 'rgba(255, 120, 0, .8)'],
                        ]}},
            {'color': {'column': 'area'}},
            {'color': {'column': 'lang',
                       'categories': {
                        'Bengali': 'hsla(0, 100%, 50%, .8)',
                        'English': 'hsla(36, 100%, 50%, .8)',
                        'Gujarati': 'hsla(72, 100%, 50%, .8)',
                        'Hindi': 'hsla(108, 100%, 50%, .8)',
                        'Kannada': 'hsla(144, 100%, 50%, .8)',
                        'Nepali': 'hsla(180, 100%, 50%, .8)',
                        'Punjabi': 'hsla(216, 100%, 50%, .8)',
                        'Tamil': 'hsla(252, 100%, 50%, .8)',
                        'Telugu': 'hsla(288, 100%, 50%, .8)',
                        'Urdu': 'hsla(324, 100%, 50%, .8)',
                        '_other': 'hsla(0, 0%, 60%, .8)',
                        }
                       }},
            {'color': {'column': 'literacy',
                       'colorstops': [
                        [60, 'rgba(20, 20, 20, .8)'],
                        [100, 'rgba(255, 120, 0, .8)'],
                        ]}},
            {'color': {'column': 'urbanity',
                       'colorstops': [
                        [10, 'rgba(20, 20, 20, .8)'],
                        [50, 'rgba(255, 120, 0, .8)'],
                        ]}},
            {'color': {'column': 'sex_ratio',
                       'colorstops': [
                        [850, 'rgba(20, 20, 255, .8)'],
                        [1050, 'rgba(255, 20, 20, .8)'],
                        ]}},
        ],
    }

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return user and user.is_previewer()
