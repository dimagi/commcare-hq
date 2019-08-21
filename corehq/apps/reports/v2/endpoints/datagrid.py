from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.apps.reports.v2.models import BaseDataEndpoint
from corehq.elastic import ESError


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

        is_timeout = False
        try:
            results = [formatter(self.request, self.domain, r).get_context()
                       for r in query.run().raw['hits'].get('hits', [])]
            took = query.run().raw.get('took')
        except ESError:
            results = []
            is_timeout = True
            took = None

        return {
            "rows": results,
            "totalRecords": total,
            'resetPagination': reset_pagination,
            "isTimeout": is_timeout,
            "took": took,
        }
