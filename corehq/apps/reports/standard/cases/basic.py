from __future__ import absolute_import
from __future__ import unicode_literals

from django.contrib import messages
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy
from elasticsearch import TransportError

from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.standard.cases.filters import CaseSearchFilter
from corehq.apps.reports.standard.cases.utils import (
    query_all_project_data,
    query_deactivated_data,
    get_case_owners,
    query_location_restricted_cases,
)
from corehq.const import SERVER_DATETIME_FORMAT
from corehq.util.timezones.conversions import PhoneTime
from memoized import memoized

from corehq.apps.es import cases as case_es
from corehq.apps.reports.api import ReportDataSource
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.exceptions import BadRequestError
from corehq.apps.reports.filters.select import SelectOpenCloseFilter
from corehq.apps.reports.filters.case_list import CaseListFilter as EMWF
from corehq.apps.reports.generic import ElasticProjectInspectionReport
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

        if self.request.can_access_all_locations and (
                EMWF.show_all_data(mobile_user_and_group_slugs)
                or EMWF.no_filters_selected(mobile_user_and_group_slugs)
        ):
            pass

        elif (self.request.can_access_all_locations
              and EMWF.show_project_data(mobile_user_and_group_slugs)):
            query = query_all_project_data(
                query, self.domain, mobile_user_and_group_slugs
            )

        elif (self.request.can_access_all_locations
              and EMWF.show_deactivated_data(mobile_user_and_group_slugs)):
            query = query_deactivated_data(query, self.domain)

        else:  # Only show explicit matches
            query = query.owner(self.case_owners)

        if not self.request.can_access_all_locations:
            query = query_location_restricted_cases(query, self.request)

        search_string = CaseSearchFilter.get_value(self.request, self.domain)
        if search_string:
            query = query.set_query({"query_string": {"query": search_string}})

        return query

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
        return get_case_owners(self.request, self.domain, mobile_user_and_group_slugs)

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

    @classmethod
    def get_subpages(cls):
        def _get_case_name(request=None, **context):
            if 'case' in context:
                return mark_safe(context['case'].name)
            else:
                return _('View Case')

        from corehq.apps.reports.views import CaseDataView
        return [
            {
                'title': _get_case_name,
                'urlname': CaseDataView.urlname,
            },
        ]

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
