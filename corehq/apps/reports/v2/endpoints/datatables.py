from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.apps.reports.v2.models import BaseDataEndpoint


class DataTablesDataEndpoint(BaseDataEndpoint):
    slug = 'datatables'

    @property
    def draw(self):
        return int(self.data.get('draw', 1))

    @property
    def start(self):
        return int(self.data.get('start', 0))

    @property
    def length(self):
        return int(self.data.get('length', 1))

    @property
    def order(self):
        return int(self.data.get('order', 1))

    def get_response(self, query, formatter):
        total = query.count()
        query = query.size(self.length).start(self.start)
        results = [formatter(self.request, self.domain, r).get_context()
                   for r in query.run().raw['hits'].get('hits', [])]
        return {
            "draw": self.draw,
            "data": results,
            "recordsTotal": total,
            "recordsFiltered": total,
        }
