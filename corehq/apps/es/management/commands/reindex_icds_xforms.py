import copy
from datetime import datetime

from django.core.management.base import BaseCommand

from corehq.elastic import get_es_new
from corehq.util.dates import iso_string_to_datetime
from elasticsearch.helpers import reindex


class Command(BaseCommand):
    help = ("Adhoc command for ICDS xforms reindex using scan and bulk insert API")

    def add_arguments(self, parser):
        parser.add_argument('index_name')
        parser.add_argument('start_date', help='in yyyy-MM-dd format')
        parser.add_argument('end_date', help='in yyyy-MM-dd format')
        parser.add_argument('scroll_timeout', help='Elasticsearch scroll timeout such as 5m, 10m or 100m etc')

    def handle(self, index_name, start_date, end_date, scroll_timeout, **options):
        es = get_es_new()
        print("Total number of docs in this date range in old index",
            self._get_doc_count(es, 'xforms', start_date, end_date))
        start_date = self._get_last_start_date(es, index_name, start_date, end_date)
        query = self._base_query(start_date, end_date)
        query.update({
            "_source": {"exclude": ["_id"]}
        })
        old_index = "xforms"  # alias
        print("Number of remaining docs to be reindexed to new index ",
            self._get_doc_count(es, 'xforms', start_date, end_date))
        print("Starting reindex ", datetime.now())
        reindex(es, old_index, index_name, query=query, chunk_size=100, scroll=scroll_timeout)
        print("Reindex finished ", datetime.now())

    def _base_query(self, start_date, end_date):
        return copy.deepcopy({
            "sort": {"received_on": {"order": "asc"}},
            "query": {
                "range": {
                    "received_on": {
                        "gte": start_date,
                        "lte": end_date,
                        "format": "yyyy-MM-dd"
                    }
                }
            },
        })

    def _get_doc_count(self, es, index, start_date, end_date):
        query = self._base_query(start_date, end_date)
        ret = es.count(index, body=query)
        return ret['count']

    def _get_last_start_date(self, es, index_name, start_date, end_date):
        query = self._base_query(start_date, end_date)
        query.update({
            "sort": {"received_on": {"order": "desc"}},
            "_source": ["received_on"],
            "from": 0,
            "size": 1
        })
        result = es.search(index_name, body=query)
        hits = result['hits']['hits']
        if not hits:
            return start_date
        else:
            new_start_date = str(iso_string_to_datetime(hits[0]['_source']['received_on']).date())
            already_index_count = self._get_doc_count(es, index_name, start_date, new_start_date)
            expected_count = self._get_doc_count(es, 'xforms', start_date, new_start_date)
            if already_index_count == expected_count:
                print(already_index_count, " docs are already indexed ")
                print("Resuming from date ", new_start_date)
                return new_start_date
            else:
                return start_date
