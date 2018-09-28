from __future__ import absolute_import
from __future__ import unicode_literals

from django.contrib import messages
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy
from elasticsearch import TransportError

from corehq.apps.locations.dbaccessors import (
    user_ids_at_locations, user_ids_at_locations_and_descendants
)
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.standard.cases.filters import CaseSearchFilter
from corehq.const import SERVER_DATETIME_FORMAT
from corehq.util.timezones.conversions import PhoneTime
from memoized import memoized

from corehq.apps.es import filters, users as user_es, cases as case_es
from corehq.apps.es.es_query import HQESQuery
from corehq.apps.locations.dbaccessors import get_users_location_ids
from corehq.apps.reports.api import ReportDataSource
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.exceptions import BadRequestError
from corehq.apps.reports.filters.select import SelectOpenCloseFilter
from corehq.apps.reports.filters.case_list import CaseListFilter as EMWF
from corehq.apps.reports.generic import ElasticProjectInspectionReport
from corehq.apps.reports.models import HQUserType
from corehq.apps.reports.standard import ProjectReportParametersMixin
from corehq.apps.reports.standard.inspect import ProjectInspectionReport
from corehq.elastic import ESError
from corehq.toggles import CASE_LIST_EXPLORER

from .data_sources import CaseInfo, CaseDisplay


class CaseListMixin(ElasticProjectInspectionReport, ProjectReportParametersMixin):
    fields = [
        'corehq.apps.reports.filters.case_list.CaseListFilter',
        'corehq.apps.reports.filters.select.CaseTypeFilter',
        'corehq.apps.reports.filters.select.SelectOpenCloseFilter',
        'corehq.apps.reports.standard.cases.filters.CaseSearchFilter',
    ]

    case_filter = {}
    ajax_pagination = True
    asynchronous = True
    search_class = case_es.CaseES

    def _build_query(self):
        query = (self.search_class()
                 .domain(self.domain)
                 .size(self.pagination.count)
                 .start(self.pagination.start))
        query.es_query['sort'] = self.get_sorting_block()
        mobile_user_and_group_slugs = self.request.GET.getlist(EMWF.slug)

        if self.case_filter:
            query = query.filter(self.case_filter)

        query = query.NOT(case_es.case_type("user-owner-mapping-case"))

        if self.case_type:
            query = query.case_type(self.case_type)

        if self.case_status:
            query = query.is_closed(self.case_status == 'closed')

        if self.request.can_access_all_locations and (EMWF.show_all_data(mobile_user_and_group_slugs) or
                                                      EMWF.no_filters_selected(mobile_user_and_group_slugs)):
            pass
        elif self.request.can_access_all_locations and EMWF.show_project_data(mobile_user_and_group_slugs):
            # Show everything but stuff we know for sure to exclude
            user_types = EMWF.selected_user_types(mobile_user_and_group_slugs)
            ids_to_exclude = self.get_special_owner_ids(
                admin=HQUserType.ADMIN not in user_types,
                unknown=HQUserType.UNKNOWN not in user_types,
                web=HQUserType.WEB not in user_types,
                demo=HQUserType.DEMO_USER not in user_types,
                commtrack=False,
            )
            query = query.NOT(case_es.owner(ids_to_exclude))
        else:  # Only show explicit matches
            query = query.owner(self.case_owners)

        if not self.request.can_access_all_locations:
            query = query.OR(self.scope_filter())

        search_string = CaseSearchFilter.get_value(self.request, self.domain)
        if search_string:
            query = query.set_query({"query_string": {"query": search_string}})

        return query

    def scope_filter(self):
        # Filter to be applied in AND with filters for export to add scope for restricted user
        # Restricts to cases owned by accessible locations and their respective users Or Cases
        # Last Modified by accessible users
        accessible_location_ids = (SQLLocation.active_objects.accessible_location_ids(
            self.request.domain,
            self.request.couch_user)
        )
        accessible_user_ids = user_ids_at_locations(accessible_location_ids)
        accessible_ids = accessible_user_ids + list(accessible_location_ids)
        return case_es.owner(accessible_ids)

    @property
    @memoized
    def es_results(self):
        try:
            return self._build_query().run().raw
        except ESError as e:
            original_exception = e.args[0]
            if isinstance(original_exception, TransportError):
                if hasattr(original_exception.info, "get"):
                    if original_exception.info.get('status') == 400:
                        raise BadRequestError()
            raise e

    def get_special_owner_ids(self, admin, unknown, web, demo, commtrack):
        if not any([admin, unknown, web, demo, commtrack]):
            return []

        user_filters = [filter_ for include, filter_ in [
            (admin, user_es.admin_users()),
            (unknown, filters.OR(user_es.unknown_users())),
            (web, user_es.web_users()),
            (demo, user_es.demo_users()),
        ] if include]

        owner_ids = (user_es.UserES()
                     .domain(self.domain)
                     .OR(*user_filters)
                     .get_ids())

        if commtrack:
            owner_ids.append("commtrack-system")
        if demo:
            owner_ids.append("demo_user_group_id")
            owner_ids.append("demo_user")
        return owner_ids

    @property
    @memoized
    def case_owners(self):
        """
        For unrestricted user
        :return:
        user ids for selected user types
        for selected reporting group ids, returns user_ids belonging to these groups
            also finds the sharing groups which has any user from the above reporting group
        selected sharing group ids
        selected user ids
            also finds the sharing groups which has any user from the above selected users
            ids and descendants ids of assigned locations to these users
        ids and descendants ids of selected locations
            assigned users at selected locations and their descendants

        For restricted user
        :return:
        selected user ids
            also finds the sharing groups which has any user from the above selected users
            ids and descendants ids of assigned locations to these users
        ids and descendants ids of selected locations
            assigned users at selected locations and their descendants
        """
        # Get user ids for each user that match the demo_user, admin,
        # Unknown Users, or All Mobile Workers filters
        mobile_user_and_group_slugs = self.request.GET.getlist(EMWF.slug)
        special_owner_ids, selected_sharing_group_ids, selected_reporting_group_users = [], [], []
        sharing_group_ids, location_owner_ids, assigned_user_ids_at_selected_locations = [], [], []
        if self.request.can_access_all_locations:
            user_types = EMWF.selected_user_types(mobile_user_and_group_slugs)
            special_owner_ids = self.get_special_owner_ids(
                admin=HQUserType.ADMIN in user_types,
                unknown=HQUserType.UNKNOWN in user_types,
                web=HQUserType.WEB in user_types,
                demo=HQUserType.DEMO_USER in user_types,
                commtrack=HQUserType.COMMTRACK in user_types,
            )

            # Get group ids for each group that was specified
            selected_reporting_group_ids = EMWF.selected_reporting_group_ids(mobile_user_and_group_slugs)
            selected_sharing_group_ids = EMWF.selected_sharing_group_ids(mobile_user_and_group_slugs)

            # Get user ids for each user in specified reporting groups
            selected_reporting_group_users = []
            if selected_reporting_group_ids:
                report_group_q = (HQESQuery(index="groups").domain(self.domain)
                                  .doc_type("Group")
                                  .filter(filters.term("_id", selected_reporting_group_ids))
                                  .fields(["users"]))
                user_lists = [group["users"] for group in report_group_q.run().hits]
                selected_reporting_group_users = list(set().union(*user_lists))

        # Get user ids for each user that was specifically selected
        selected_user_ids = EMWF.selected_user_ids(mobile_user_and_group_slugs)

        # Show cases owned by any selected locations, user locations, or their children
        loc_ids = set(EMWF.selected_location_ids(mobile_user_and_group_slugs))

        if loc_ids:
            # Get users at selected locations and descendants
            assigned_user_ids_at_selected_locations = user_ids_at_locations_and_descendants(loc_ids)
            # Get user ids for each user in specified reporting groups

        if selected_user_ids:
            loc_ids.update(get_users_location_ids(self.domain, selected_user_ids))

        location_owner_ids = []
        if loc_ids:
            location_owner_ids = SQLLocation.objects.get_locations_and_children_ids(loc_ids)

        sharing_group_ids = []
        if selected_reporting_group_users or selected_user_ids:
            # Get ids for each sharing group that contains a user from selected_reporting_group_users
            # OR a user that was specifically selected
            sharing_group_ids = (HQESQuery(index="groups")
                                 .domain(self.domain)
                                 .doc_type("Group")
                                 .term("case_sharing", True)
                                 .term("users", (selected_reporting_group_users +
                                                 selected_user_ids))
                                 .get_ids())

        owner_ids = list(set().union(
            special_owner_ids,
            selected_user_ids,
            selected_sharing_group_ids,
            selected_reporting_group_users,
            sharing_group_ids,
            location_owner_ids,
            assigned_user_ids_at_selected_locations,
        ))
        return owner_ids

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


@location_safe
class CaseListReport(CaseListMixin, ProjectInspectionReport, ReportDataSource):

    # note that this class is not true to the spirit of ReportDataSource; the whole
    # point is the decouple generating the raw report data from the report view/django
    # request. but currently these are too tightly bound to decouple

    name = ugettext_lazy('Case List')
    slug = 'case_list'

    @property
    def view_response(self):
        if self.request.couch_user.is_dimagi and not CASE_LIST_EXPLORER.enabled(self.domain):
            messages.warning(
                self.request,
                'Hey Dimagi User! Have you tried out the <a href="https://confluence.dimagi.com/display/ccinternal/Case+List+Explorer" target="_blank">Case List Explorer</a> yet? It might be just what you are looking for!',
                extra_tags='html',
            )
        return super(CaseListReport, self).view_response

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

    def get_data(self):
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
            DataTablesColumn(_("Name"), prop_name="name.exact", css_class="case-name-link"),
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
            return (PhoneTime(date, self.timezone).user_time(self.timezone)
                    .ui_string(SERVER_DATETIME_FORMAT))
        else:
            return ''
