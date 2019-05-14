from __future__ import absolute_import
from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy

from corehq.apps.reports.standard.cases.utils import (
    query_all_project_data,
    query_deactivated_data,
    get_case_owners,
)
from corehq.apps.reports.v2.endpoints.case_owner import CaseOwnerEndpoint
from corehq.apps.reports.v2.models import BaseReportFilter
from corehq.apps.reports.filters.case_list import CaseListFilter as EMWF


class CaseOwnerReportFilter(BaseReportFilter):
    title = ugettext_lazy("Case Owner(s)")
    name = 'report_case_owner'
    endpoint_slug = CaseOwnerEndpoint.slug

    @classmethod
    def get_context(cls):
        return {
            'title': cls.title,
            'name': cls.name,
            'endpointSlug': cls.endpoint_slug,
        }

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

        # otherwise only return explicit matches
        case_owners = get_case_owners(self.request, self.domain, self.value)
        return query.owner(case_owners)
