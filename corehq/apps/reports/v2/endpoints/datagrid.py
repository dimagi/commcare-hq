from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.apps.reports.v2.models import BaseDataEndpoint


class DatagridEndpoint(BaseDataEndpoint):
    slug = 'datagrid'

    @property
    def page(self):
        return int(self.data.get('page', 1))

    @property
    def limit(self):
        return int(self.data.get('limit', 10))

    @property
    def current_total(self):
        return int(self.data.get('totalRecords', 0))

    def get_response(self, query, formatter):
        reset_pagination = False
        total = query.count()
        start = (self.page - 1) * self.limit

        if start > total or self.current_total != total:
            start = 0
            reset_pagination = True

        query = query.size(self.limit).start(start)
        results = [formatter(self.request, self.domain, r).get_context()
                   for r in query.run().raw['hits'].get('hits', [])]
        return {
            "rows": results,
            "totalRecords": total,
            'resetPagination': reset_pagination,
        }
