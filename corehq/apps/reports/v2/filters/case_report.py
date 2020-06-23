from django.utils.translation import ugettext_lazy

from corehq.apps.commtrack.const import USER_LOCATION_OWNER_MAP_TYPE
from corehq.apps.es import CaseSearchES
from corehq.apps.es import cases as case_es
from corehq.apps.reports.filters.case_list import CaseListFilter as EMWF
from corehq.apps.reports.standard.cases.utils import (
    get_case_owners,
    query_all_project_data,
    query_deactivated_data,
)
from corehq.apps.reports.v2.endpoints.case_owner import CaseOwnerEndpoint
from corehq.apps.reports.v2.endpoints.case_type import CaseTypeEndpoint
from corehq.apps.reports.v2.models import (
    BaseReportFilter,
    ReportFilterKoTemplate,
)


class CaseOwnerReportFilter(BaseReportFilter):
    title = ugettext_lazy("Case Owner(s)")
    name = 'report_case_owner'
    endpoint_slug = CaseOwnerEndpoint.slug
    ko_template_name = ReportFilterKoTemplate.SELECT2_MULTI_ASYNC

    def get_filtered_query(self, query):
        if self.request.can_access_all_locations and (
            EMWF.show_all_data(self.value)
            or EMWF.no_filters_selected(self.value)
        ):
            return query

        if self.request.can_access_all_locations and EMWF.show_project_data(self.value):
            return query_all_project_data(query, self.domain, self.value)

        if self.request.can_access_all_locations and EMWF.show_deactivated_data(self.value):
            return query_deactivated_data(query, self.domain)

        selected_user_types = [v['id'] for v in self.value]
        case_owners = get_case_owners(self.request, self.domain, selected_user_types)
        return query.owner(case_owners)


class CaseTypeReportFilter(BaseReportFilter):
    title = ugettext_lazy("Case Type")
    name = 'report_case_type'
    endpoint_slug = CaseTypeEndpoint.slug
    ko_template_name = ReportFilterKoTemplate.SELECT2_SINGLE

    @classmethod
    def initial_value(cls, request, domain):
        initial_value = super(CaseTypeReportFilter, cls).initial_value(request, domain)
        if initial_value is None:
            query = (CaseSearchES().domain(domain)
                     .NOT(case_es.case_type(USER_LOCATION_OWNER_MAP_TYPE)))
            result = query.size(1).values_list('type', flat=True)
            initial_value = result[0] if len(result) > 0 else None
        return initial_value

    def get_filtered_query(self, query):
        if self.value is None:
            return query
        return query.case_type(self.value)
