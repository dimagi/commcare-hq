import copy
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand

from corehq.elastic import get_es_new
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
        new_docs_count = self._get_doc_count(self.new_index, start_date, end_date)
        print("Number of docs in old index",
            old_docs_count)
        print("Number of docs in new index",
            new_docs_count)
        if print_counts:
            return

        if old_docs_count == new_docs_count:
            print("Doc counts same, nothing left to reindex. Exiting!")
            return

        for query in self._breakup_by_intervals(start_date, end_date):
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

    def _breakup_by_intervals(self, start_date, end_date, interval_format='hour'):
        assert interval_format in ['hour', 'minute']
        query = self._base_query(start_date, end_date, 'yyyy-MM-dd HH:mm:ss' if interval_format is 'minute' else "yyyy-MM-dd")
        query.update({
            "aggs": {
                "by_interval": {
                    "date_histogram": {
                        "field": "received_on",
                        "interval": interval_format
                    }
                }
            }
        })

        def get_counts_by_interval(index):
            print("Getting doc counts from index", index, "for each", interval_format)
            counts_by_interval = {}
            results = self.es.search(index, body=query)['aggregations']['by_interval']['buckets']
            for result in results:
                interval_epoch = result['key']
                interval_start = datetime.utcfromtimestamp(interval_epoch / 1000)
                count = result['doc_count']
                counts_by_interval[interval_start] = count
            return counts_by_interval

        counts_by_interval_old_index = get_counts_by_interval(self.old_index)
        counts_by_interval_new_index = get_counts_by_interval(self.new_index)

        collate_start_time = None
        collate_end_time = None
        for interval_start, count in counts_by_interval_old_index.items():
            delta = timedelta(hours=1) if interval_format is 'hour' else timedelta(minutes=1)
            start_time = interval_start.strftime('%Y-%m-%d %H:%M:%S')
            end_time = (interval_start + delta).strftime('%Y-%m-%d %H:%M:%S')
            collate_start_time = collate_start_time or start_time
            collate_end_time = collate_end_time or end_time
            count_in_new_index = counts_by_interval_new_index.get(interval_start, 0)
            if count_in_new_index != count:
                if interval_format == 'minute':
                    if start_time == collate_end_time:
                        collate_end_time = end_time
                    else:
                        yield self._base_query(
                            collate_start_time, collate_end_time, 'yyyy-MM-dd HH:mm:ss'
                        )
                        collate_start_time = start_time
                        collate_end_time = end_time
                else:
                    for query in self._breakup_by_intervals(start_time, end_time, 'minute'):
                        yield query
            else:
                print("Already reindexed. Docs count is ", count, count_in_new_index, "Skipping the interval of ", interval_format, start_time, end_time)

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
