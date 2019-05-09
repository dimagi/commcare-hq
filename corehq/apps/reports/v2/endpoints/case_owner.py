from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.apps.reports.filters.controllers import (
    CaseListFilterOptionsController,
)
from corehq.apps.reports.v2.models import BaseOptionsEndpoint


class CaseOwnerEndpoint(BaseOptionsEndpoint):
    slug = "case_owner"

    @property
    def search(self):
        return self.data.get('search', '')

    @property
    def page(self):
        return self.data.get('page', 1)

    def get_response(self):
        options_controller = CaseListFilterOptionsController(
            self.request, self.domain, self.search
        )
        has_more, results = options_controller.get_options(show_more=True)
        return {
            'results': results,
            'pagination': {
                'more': has_more,
            }
        }
