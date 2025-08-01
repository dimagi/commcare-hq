from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from memoized import memoized

from corehq.apps.es import cases as case_es
from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.api import ReportDataSource
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.exceptions import BadRequestError, TooManyOwnerIDsError
from corehq.apps.reports.filters.case_list import CaseListFilter as EMWF
from corehq.apps.reports.filters.select import SelectOpenCloseFilter
from corehq.apps.reports.generic import ElasticProjectInspectionReport
from corehq.apps.reports.standard import (
    ProjectReport,
    ProjectReportParametersMixin,
)
from corehq.apps.reports.standard.cases.filters import CaseSearchFilter
from corehq.apps.reports.standard.cases.utils import (
    add_case_owners_and_location_access,
)
from corehq.elastic import ESError
from corehq.util.es.elasticsearch import TransportError

from .data_sources import CaseDisplayES


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

    def _base_query(self):
        if getattr(self, 'rendered_as', None) == 'export':
            search_class = self.search_class(for_export=True)
        else:
            search_class = self.search_class()
        return (
            search_class
            .domain(self.domain)
            .size(self.pagination.count)
            .start(self.pagination.start)
        )

    def _build_query(self):
        query = self._base_query()
        query.es_query['sort'] = self.get_sorting_block()
        mobile_user_and_group_slugs = self.get_request_param(EMWF.slug, as_list=True)

        if self.case_filter:
            query = query.filter(self.case_filter)

        query = query.NOT(case_es.case_type("user-owner-mapping-case"))

        if self.case_types:
            query = query.case_type(self.case_types)

        if self.case_status:
            query = query.is_closed(self.case_status == 'closed')

        query = add_case_owners_and_location_access(
            query,
            self.request.domain,
            self.request.couch_user,
            self.request.can_access_all_locations,
            mobile_user_and_group_slugs
        )

        search_string = CaseSearchFilter.get_value(self.request, self.domain)
        if search_string:
            query = query.set_query({"query_string": {"query": search_string}})

        return query

    @property
    @memoized
    def es_results(self):
        try:
            return self._run_es_query()
        except ESError as e:
            original_exception = e.args[0]
            if isinstance(original_exception, TransportError):
                if hasattr(original_exception.info, "get"):
                    if original_exception.info.get('status') == 400:
                        raise BadRequestError()
            raise e
        except TooManyOwnerIDsError:
            raise BadRequestError(
                _("Cannot filter by that many case owners. Choose a more specific group or location.")
            )

    def _run_es_query(self):
        return self._build_query().run().raw

    def get_case(self, row):
        if '_source' in row:
            case_dict = row['_source']
        else:
            raise ValueError("Case object is not in search result %s" % row)

        if case_dict['domain'] != self.domain:
            raise Exception(
                f"case.domain != self.domain; {case_dict['domain']!r} and "
                f"{self.domain!r}, respectively"
            )

        return case_dict

    @property
    def shared_pagination_GET_params(self):
        shared_params = super().shared_pagination_GET_params
        shared_params.append(dict(
            name=SelectOpenCloseFilter.slug,
            value=self.get_request_param(SelectOpenCloseFilter.slug, ''),
        ))
        return shared_params


@location_safe
class CaseListReport(CaseListMixin, ProjectReport, ReportDataSource):

    # note that this class is not true to the spirit of ReportDataSource; the whole
    # point is the decouple generating the raw report data from the report view/django
    # request. but currently these are too tightly bound to decouple

    name = gettext_lazy('Case List')
    description = gettext_lazy('View all cases within your project space.')
    slug = 'case_list'
    use_bootstrap5 = True

    @classmethod
    def get_subpages(cls):
        def _get_case_name(request=None, **context):
            if 'case' in context and context['case'].name:
                return context['case'].name
            else:
                return _('View Case')

        from corehq.apps.reports.standard.cases.case_data import CaseDataView
        return [
            {
                'title': _get_case_name,
                'urlname': CaseDataView.urlname,
            },
        ]

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

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(_("Case Type"), prop_name="type.exact",
                             use_bootstrap5=self.use_bootstrap5),
            DataTablesColumn(_("Name"), prop_name="name.exact", css_class="case-name-link",
                             use_bootstrap5=self.use_bootstrap5),
            DataTablesColumn(_("Owner"), prop_name="owner_display", sortable=False,
                             use_bootstrap5=self.use_bootstrap5),
            DataTablesColumn(_("Created Date"), prop_name="opened_on",
                             use_bootstrap5=self.use_bootstrap5),
            DataTablesColumn(_("Created By"), prop_name="opened_by_display", sortable=False,
                             use_bootstrap5=self.use_bootstrap5),
            DataTablesColumn(_("Modified Date"), prop_name="modified_on",
                             use_bootstrap5=self.use_bootstrap5),
            DataTablesColumn(_("Status"), prop_name="get_status_display", sortable=False,
                             use_bootstrap5=self.use_bootstrap5)
        )
        headers.custom_sort = [[5, 'desc']]
        return headers

    @property
    def rows(self):
        for row in self.es_results['hits'].get('hits', []):
            display = CaseDisplayES(self.get_case(row), self.timezone, self.individual)

            yield [
                display.case_type,
                display.case_link,
                display.owner_display,
                display.opened_on,
                display.creating_user,
                display.modified_on,
                display.closed_display
            ]
