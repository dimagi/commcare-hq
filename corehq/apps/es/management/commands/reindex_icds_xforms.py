import copy
import time
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand

from corehq.elastic import get_es_export
from elasticsearch.helpers import reindex
from corehq.util.es.elasticsearch import ConnectionTimeout


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
        parser.add_argument('--scroll_timeout', default='60m',
            help='Elasticsearch scroll timeout such as 5m, 10m or 100m etc')
        parser.add_argument('--chunk_size', default=100, type=int)
        parser.add_argument(
            '--print_counts',
            action='store_true',
            default=False,
            help="Simply print doc counts and exit"
        )
        parser.add_argument(
            '--hours_interval_only',
            action='store_true',
            default=False,
            help="(Doesn't work) Skip checking doc counts before reindexing. Applicable with native only"
        )

    def handle(self, index_name, start_date, end_date, **options):
        self.es = get_es_export()
        self.new_index = index_name
        self.old_index = "xforms"  # alias
        scroll_timeout = options.get('scroll_timeout')
        chunk_size = options.get('chunk_size')
        print_counts = options.get('print_counts')
        use_native_api = options.get('native')
        hours_interval_only = False
        old_docs_count = self._get_doc_count(self.old_index, start_date, end_date)
        new_docs_count = self._get_doc_count(self.new_index, start_date, end_date)
        if new_docs_count / old_docs_count < 0.3:
            hours_interval_only = True
        print("Number of docs in old index",
            old_docs_count)
        print("Number of docs in new index",
            new_docs_count)
        if print_counts:
            return

        if old_docs_count == new_docs_count:
            print("Doc counts same, nothing left to reindex. Exiting!")
            return

        for query in self._breakup_by_intervals(start_date, end_date, 'hour', hours_interval_only):
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
                    query=query, chunk_size=chunk_size, scroll=scroll_timeout,
                    scan_kwargs={'request_timeout': 600})
            print("Reindex finished ", datetime.now())

    def _breakup_by_intervals(self, start_date, end_date, interval_format='hour', hours_interval_only=False):
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

            if interval_format == 'hour':
                if count_in_new_index != count:
                    if hours_interval_only:
                        yield self._base_query(start_time, end_time, 'yyyy-MM-dd HH:mm:ss')
                    else:
                        for query in self._breakup_by_intervals(start_time, end_time, 'minute'):
                            yield query
                else:
                    print("Skipping already reindexed hour ", interval_start)
            else:
                is_last_minute = interval_start.minute == 59

                if count_in_new_index != count:
                    collate_end_time = end_time
                    if is_last_minute:
                        yield self._base_query(
                            collate_start_time, collate_end_time, 'yyyy-MM-dd HH:mm:ss'
                        )
                    else:
                        print("Collating to ", collate_start_time, collate_end_time)
                else:
                    print("Skipping already reindexed minute ", interval_start)
                    if collate_end_time != end_time or is_last_minute:
                        yield self._base_query(
                            collate_start_time, collate_end_time, 'yyyy-MM-dd HH:mm:ss'
                        )
                    collate_start_time = None
                    collate_end_time = None

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
        result = self.es.reindex(reindex_query, wait_for_completion=False, request_timeout=300)
        print("Result task is ", result)
        task_id = result['task']
        node_id = task_id.split(":")[0]
        task_finished = False
        no_progress_loops = 0
        last_updated_count = 0
        last_create_count = 0
        while not task_finished:
            try:
                task = self.es.tasks.list(task_id=task_id, params={'detailed': True})['nodes'][node_id]['tasks'][task_id]
                status = task['status']
                print("Updated/Created/Total: ", status['updated'], status['created'], status['total'])
                if last_updated_count != status['updated'] or last_create_count != status['created']:
                    last_updated_count = status['updated']
                    last_create_count = status['created']
                    # reset progress
                    no_progress_loops = 0
                else:
                    no_progress_loops += 1
                if no_progress_loops == 3:
                    self.es.tasks.cancel(task_id=task_id)
                    raise Exception("Cancelling task that didn't progress in last 1 min {}".format(str(query)))
                running_time_in_mins = (task['running_time_in_nanos'] / 60000000000)
                print("Running time total in mins ", running_time_in_mins)
            except Exception as e:
                task_finished = True
                print(e)
                print("This could mean task finished succesfully")
            time.sleep(20)


    def _get_doc_count(self, index, start_date, end_date):
        query = self._base_query(start_date, end_date)
        ret = self.es.count(index, body=query)
        return ret['count']
