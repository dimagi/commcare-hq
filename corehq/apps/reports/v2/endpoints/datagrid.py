from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.apps.reports.v2.models import BaseDataEndpoint


class DatagridEndpoint(BaseDataEndpoint):
    slug = 'datagrid'

    @property
    def draw(self):
        return int(self.data.get('draw', 1))

    @property
    def page(self):
        return int(self.data.get('page', 1))

    @property
    def limit(self):
        return int(self.data.get('limit', 10))

    def get_response(self, query, formatter):
        total = query.count()
        start = min((self.page - 1) * self.limit, total)

        query = query.size(self.limit).start(start)
        results = [formatter(self.request, self.domain, r).get_context()
                   for r in query.run().raw['hits'].get('hits', [])]
        return {
            "rows": results,
            "totalRecords": total,
        }
