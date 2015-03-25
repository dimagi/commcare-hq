import logging
import json

from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop

from couchdbkit import RequestFailed
from corehq.util.timezones.conversions import PhoneTime
from dimagi.utils.decorators.memoized import memoized

from corehq.apps.api.es import CaseES
from corehq.apps.es import filters
from corehq.apps.es import users as user_es
from corehq.apps.es.es_query import HQESQuery
from corehq.apps.reports.api import ReportDataSource
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.search import SearchFilter
from corehq.apps.reports.filters.select import SelectOpenCloseFilter
from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilterWithAllData as EMWF
from corehq.apps.reports.generic import ElasticProjectInspectionReport
from corehq.apps.reports.models import HQUserType
from corehq.apps.reports.standard import ProjectReportParametersMixin
from corehq.apps.reports.standard.inspect import ProjectInspectionReport

from .data_sources import CaseInfo, CaseDisplay


class CaseListMixin(ElasticProjectInspectionReport, ProjectReportParametersMixin):
    fields = [
        'corehq.apps.reports.filters.users.ExpandedMobileWorkerFilterWithAllData',
        'corehq.apps.reports.filters.select.CaseTypeFilter',
        'corehq.apps.reports.filters.select.SelectOpenCloseFilter',
        'corehq.apps.reports.standard.cases.filters.CaseSearchFilter',
    ]

    case_filter = {}
    ajax_pagination = True
    asynchronous = True

    @property
    @memoized
    def case_es(self):
        return CaseES(self.domain)

    def build_query(self, case_type=None, afilter=None, status=None, owner_ids=None, user_ids=None, search_string=None):
        owner_ids = owner_ids or []
        user_ids = user_ids or []

        def _filter_gen(key, flist):
            return {"terms": {
                key: [item.lower() for item in flist if item]
            }}

        def _domain_term():
            return {"term": {"domain.exact": self.domain}}

        subterms = [_domain_term(), afilter] if afilter else [_domain_term()]
        if case_type:
            subterms.append({"term": {"type.exact": case_type}})

        if status:
            subterms.append({"term": {"closed": (status == 'closed')}})


        if not EMWF.show_all_data(self.request):
            owner_filters = _filter_gen('owner_id', owner_ids)
            user_filters = _filter_gen('user_id', user_ids)
            filters = filter(None, [owner_filters, user_filters])
            if filters:
                subterms.append({'or': filters})

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
        query = self.build_query(case_type=self.case_type, afilter=self.case_filter,
                                 status=self.case_status, owner_ids=self.case_owners,
                                 search_string=SearchFilter.get_value(self.request, self.domain))

        query_results = case_es.run_query(query)

        if 'hits' not in query_results:
            logging.error("CaseListMixin query error: %s, urlpath: %s, params: %s, user: %s yielded a result indicating a query error: %s, results: %s" % (
                self.__class__.__name__,
                self.request.path,
                self.request.GET.urlencode(),
                self.request.couch_user.username,
                json.dumps(query),
                json.dumps(query_results)
            ))
            raise RequestFailed
        return query_results

    @property
    @memoized
    def case_owners(self):

        # Get user ids for each user that match the demo_user, admin, Unknown Users, or All Mobile Workers filters
        user_types = EMWF.selected_user_types(self.request)
        user_type_filters = []
        if HQUserType.ADMIN in user_types:
            user_type_filters.append(user_es.admin_users())
        if HQUserType.UNKNOWN in user_types:
            user_type_filters.append(user_es.unknown_users())
            user_type_filters.append(user_es.web_users())
        if HQUserType.DEMO_USER in user_types:
            user_type_filters.append(user_es.demo_users())
        if HQUserType.REGISTERED in user_types:
            user_type_filters.append(user_es.mobile_users())

        if len(user_type_filters) > 0:
            special_q = user_es.UserES().domain(self.domain).OR(*user_type_filters).show_inactive()
            special_user_ids = special_q.run().doc_ids
        else:
            special_user_ids = []

        # Get user ids for each user that was specifically selected
        selected_user_ids = EMWF.selected_user_ids(self.request)

        # Get group ids for each group that was specified
        selected_reporting_group_ids = EMWF.selected_reporting_group_ids(self.request)
        selected_sharing_group_ids = EMWF.selected_sharing_group_ids(self.request)

        # Get user ids for each user in specified reporting groups
        report_group_q = HQESQuery(index="groups").domain(self.domain)\
                                           .doc_type("Group")\
                                           .filter(filters.term("_id", selected_reporting_group_ids))\
                                           .fields(["users"])
        user_lists = [group["users"] for group in report_group_q.run().hits]
        selected_reporting_group_users = list(set().union(*user_lists))

        # Get ids for each sharing group that contains a user from selected_reporting_group_users OR a user that was specifically selected
        share_group_q = HQESQuery(index="groups").domain(self.domain)\
                                                .doc_type("Group")\
                                                .filter(filters.term("case_sharing", True))\
                                                .filter(filters.term("users", selected_reporting_group_users+selected_user_ids+special_user_ids))\
                                                .fields([])
        sharing_group_ids = share_group_q.run().doc_ids

        owner_ids = list(set().union(
            special_user_ids,
            selected_user_ids,
            selected_sharing_group_ids,
            selected_reporting_group_users,
            sharing_group_ids
        ))
        if HQUserType.COMMTRACK in user_types:
            owner_ids.append("commtrack-system")
        if HQUserType.DEMO_USER in user_types:
            owner_ids.append("demo_user_group_id")

        owner_ids += self.location_sharing_owner_ids()
        owner_ids += self.location_reporting_owner_ids()
        return owner_ids

    def location_sharing_owner_ids(self):
        """
        For now (and hopefully for always) the only owner
        id that is important for case sharing group selection
        is that actual group id.
        """
        return EMWF.selected_location_sharing_group_ids(self.request)

    def location_reporting_owner_ids(self):
        """
        Include all users that are assigned to the selected
        locations or those locations descendants.
        """
        from corehq.apps.locations.models import SQLLocation, LOCATION_REPORTING_PREFIX
        from corehq.apps.users.models import CommCareUser
        results = []
        selected_location_group_ids = EMWF.selected_location_reporting_group_ids(self.request)

        for group_id in selected_location_group_ids:
            loc = SQLLocation.objects.get(
                location_id=group_id.replace(LOCATION_REPORTING_PREFIX, '')
            )

            for l in [loc] + list(loc.get_descendants()):
                users = CommCareUser.get_db().view(
                    'locations/users_by_location_id',
                    startkey=[l.location_id],
                    endkey=[l.location_id, {}],
                    include_docs=True
                ).all()
                results += [u['id'] for u in users]

        return results

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


class CaseListReport(CaseListMixin, ProjectInspectionReport, ReportDataSource):

    # note that this class is not true to the spirit of ReportDataSource; the whole
    # point is the decouple generating the raw report data from the report view/django
    # request. but currently these are too tightly bound to decouple

    name = ugettext_noop('Case List')
    slug = 'case_list'

    @classmethod
    def display_in_dropdown(cls, domain=None, project=None, user=None):
        if project and project.commtrack_enabled:
            return False
        else:
            return True

    def slugs(self):
        return [
            '_case',
            'case_id',
            'case_name',
            'case_type',
            'detail_url',
            'is_open',
            'opened_on',
            'modified_on',
            'closed_on',
            'creator_id',
            'creator_name',
            'owner_type',
            'owner_id',
            'owner_name',
            'external_id',
        ]

    def get_data(self, slugs=None):
        for row in self.es_results['hits'].get('hits', []):
            case = self.get_case(row)
            ci = CaseInfo(self, case)
            data = {
                '_case': case,
                'detail_url': ci.case_detail_url,
            }
            data.update((prop, getattr(ci, prop)) for prop in (
                    'case_type', 'case_name', 'case_id', 'external_id',
                    'is_closed', 'opened_on', 'modified_on', 'closed_on',
                ))

            creator = ci.creating_user or {}
            data.update({
                'creator_id': creator.get('id'),
                'creator_name': creator.get('name'),
            })
            owner = ci.owner
            data.update({
                'owner_type': owner[0],
                'owner_id': owner[1]['id'],
                'owner_name': owner[1]['name'],
            })

            yield data

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
        headers.custom_sort = [[5, 'desc']]
        return headers

    @property
    def rows(self):
        for data in self.get_data():
            display = CaseDisplay(self, data['_case'])

            yield [
                display.case_type,
                display.case_link,
                display.owner_display,
                display.opened_on,
                display.creating_user,
                display.modified_on,
                display.closed_display
            ]

    def date_to_json(self, date):
        if date:
            return PhoneTime(date, self.timezone).user_time(self.timezone).done().strftime('%Y-%m-%d %H:%M:%S')
        else:
            return ''
