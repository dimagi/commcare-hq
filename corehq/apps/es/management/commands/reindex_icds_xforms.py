import copy
from datetime import datetime, timedelta

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
        parser.add_argument(
            '--native',
            action='store_true',
            default=False,
            help="""By default reindex is done via scan/bulk-insert helper. Use this
                 option to reindex using ES reindex api instead"""
        )
        parser.add_argument('--scroll_timeout', default='10m',
            help='Elasticsearch scroll timeout such as 5m, 10m or 100m etc')
        parser.add_argument('--chunk_size', default=100, type=int)
        parser.add_argument(
            '--print_counts',
            action='store_true',
            default=False,
            help="Simply print doc counts and exit"
        )

    def handle(self, index_name, start_date, end_date, **options):
        self.es = get_es_new()
        self.new_index = index_name
        self.old_index = "xforms"  # alias
        scroll_timeout = options.get('scroll_timeout')
        chunk_size = options.get('chunk_size')
        print_counts = options.get('print_counts')
        use_native_api = options.get('native')
        old_docs_count = self._get_doc_count(self.old_index, start_date, end_date)
        print("Number of docs in old index",
            old_docs_count)
        print("Number of docs in new index",
            self._get_doc_count(self.new_index, start_date, end_date))
        if print_counts:
            return

        for query in self._breakup_by_hours(start_date, end_date):
            query.update({
                "_source": {"exclude": ["_id"]}
            })
            print("Starting reindex at ", datetime.now())
            print("Query issued is ", query)
            if use_native_api:
                print("Using native reindex")
                self.reindex_using_es_api(query)
            else:
                reindex(self.es, self.old_index, self.new_index,
                    query=query, chunk_size=chunk_size, scroll=scroll_timeout)
            print("Reindex finished ", datetime.now())

    def _breakup_by_hours(self, start_date, end_date):
        query = self._base_query(start_date, end_date)
        query.update({
            "aggs": {
                "by_hour": {
                    "date_histogram": {
                        "field": "received_on",
                        "interval": "hour"
                    }
                }
            }
        })

        def get_counts_by_hour(index):
            print("Getting doc counts by hourly from index", index)
            counts_by_hour = {}
            results = self.es.search(index, body=query)['aggregations']['by_hour']['buckets']
            for result in results:
                hour_epoch = result['key']
                from_hour = datetime.utcfromtimestamp(hour_epoch / 1000)
                count = result['doc_count']
                counts_by_hour[from_hour] = count
            return counts_by_hour

        counts_by_hour_old_index = get_counts_by_hour(self.old_index)
        counts_by_hour_new_index = get_counts_by_hour(self.new_index)

        for hour, count in counts_by_hour_old_index.items():
            start_time = hour.strftime('%Y-%m-%d %H:%M:%S')
            end_time = (hour + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
            if counts_by_hour_new_index[hour] != count:
                yield self._base_query(
                    start_time, end_time, 'yyyy-MM-dd HH:mm:ss'
                )
            else:
                print("Already reindexed. Skipping the hour of ", start_time)

    def _base_query(self, start_date, end_date, format="yyyy-MM-dd"):
        return copy.deepcopy({
            "query": {
                "range": {
                    "received_on": {
                        "gte": start_date,
                        "lt": end_date,
                        "format": format
                    }
                }
            },
        })

    def reindex_using_es_api(self, query):
        reindex_query = {
            "source": {
                "index": self.old_index,
                "_source": {"exclude": ["_id"]}
            },
            "dest": {"index": self.new_index},
            "conflicts": "proceed"
        }
        reindex_query['source'].update(query)
        result = self.es.reindex(reindex_query, wait_for_completion=True, request_timeout=300)
        print("Result task is ", result)

    def _get_doc_count(self, index, start_date, end_date):
        query = self._base_query(start_date, end_date)
        ret = self.es.count(index, body=query)
        return ret['count']
