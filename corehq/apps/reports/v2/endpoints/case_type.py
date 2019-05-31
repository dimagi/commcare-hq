from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.apps.commtrack.const import USER_LOCATION_OWNER_MAP_TYPE
from corehq.apps.reports.analytics.esaccessors import (
    get_case_search_types_for_domain_es,
)
from corehq.apps.reports.v2.models import BaseOptionsEndpoint


class CaseTypeEndpoint(BaseOptionsEndpoint):
    slug = "case_type"

    @staticmethod
    def _fmt_option(case_type):
        return {
            'id': case_type,
            'text': case_type,
        }

    @property
    def options(self):
        case_types = get_case_search_types_for_domain_es(self.domain)
        return [self._fmt_option(case_type) for case_type in case_types
                if case_type != USER_LOCATION_OWNER_MAP_TYPE]

    def get_response(self):
        return {
            'options': self.options,
        }
