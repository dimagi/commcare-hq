import copy
import json
import requests
import time
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand

from corehq.elastic import get_es_export, ES_META
from elasticsearch.helpers import reindex
from corehq.util.es.elasticsearch import ConnectionTimeout

USAGE = """Reindex data into local Elasticsearch v7 cluster from remote
Elasticsearch v2 cluster using Elasticsearch reindex API
https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-reindex.html#reindex-from-remote

The localsettings from where this command is run must point to Elasticsearch7 host,
which is considered as local host.

The index to be reindexed and the remote host are required
"""


class Command(BaseCommand):
    help = USAGE

    def add_arguments(self, parser):
        parser.add_argument(
            "index_name",
            help="Index to be reindexed. Should be one of " + ", ".join(ES_META.keys()),
        )
        parser.add_argument(
            "es2_remote_host",
            help="Remote ES2 host in http://otherhost:9200 format"
        )
        parser.add_argument(
            "--start_date",
            default=None,
            help="start date (inclusive) to reindex docs based on inserted_at field."
                 "This is supported only for Form and Case indices."
                 "Default is 2000-01-01. In yyyy-MM-dd format"
        )
        parser.add_argument(
            "--end_date",
            default=None,
            help="end date (inclusive) to reindex docs based on inserted_at field."
                 "This is supported only for Form and Case indices."
                 "Default is today. In yyyy-MM-dd format"
        )
        parser.add_argument(
            "--chunk_size",
            default=100,
            type=int,
            help=""
        )
        parser.add_argument(
            "--print_index_size",
            action="store_true",
            default=False,
            help="Print number of docs in remote and new cluster"
        )

    def handle(self, index_name, es2_remote_host, **options):
        assert index_name in ES_META
        self.index_info = ES_META[index_name]
        self.index = self.index_info.index
        self.es2_remote_host = es2_remote_host
        # Cancelled/failed reindex queries are tracked to be retried
        self.cancelled_queries = []
        if index_name not in ["forms", "cases"] and (options.get('start_date') or options.get('end_date')):
            raise CommandError("start and end dates are supported only for form/case indices")

        self.es = get_es_export()

        if index_name in ["forms", "cases"]:
            start_date = options.get('start_date') or '2000-01-01'
            end_date = options.get('end_date') or datetime.today().strftime('%Y-%m-%d')
        else:
            start_date, end_date = None, None
        local_count = self.get_es7_count(start_date, end_date)
        remote_count = self.get_es2_count(start_date, end_date)
        print("Number of docs in remote ES2 index", remote_count)
        print("Number of docs in local ES7 index", local_count)

        if options.get("print_index_size"):
            return
        elif local_count == remote_count:
            print("Doc counts are same, nothing left to reindex. Exiting!")
            return
        else:
            self.reindex(start_date, end_date)

    def reindex(self, start_date=None, end_date=None):
        if start_date and end_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
            assert end_date >= start_date

        reindex_query = {
            "source": {
                "remote": {
                    "host": self.es2_remote_host
                },
                "index": self.index,
                "_source": {"exclude": ["_id"]}
            },
            "dest": {"index": self.index},
            "conflicts": "proceed"
        }

        if start_date and end_date:
            days = (end_date - start_date).days
            for start in (start_date + timedelta(days=n) for n in range(days+1)):
                end = start + timedelta(days=1)
                local_count = self.get_es7_count(start, end)
                remote_count = self.get_es2_count(start, end)
                if local_count == remote_count:
                    print("Skipping for date {d} as doc counts are equal ({c})".format(d=start, c=local_count))
                    continue
                reindex_query["source"].update(self._range_query(start, end))
                print("Reindexing for date {d}".format(d=start))
                self.reindex_and_poll_progress(reindex_query)
        else:
            print("Starting reindex for index {i}".format(i=self.index))
            self.reindex_and_poll_progress(reindex_query)

    def reindex_and_poll_progress(self, reindex_query):
        # Initialize reindex and poll the reindex status using the tasks API
        # Cancels the queries if the reindex is stuck for any reason and tracks it
        # under self.cancelled_queries to be prompted for retry
        print("query is ", reindex_query)
        result = self.es.reindex(reindex_query, wait_for_completion=False, request_timeout=300)
        print("Result task is ", result)
        task_id = result["task"]
        node_id = task_id.split(":")[0]
        task_finished = False
        no_progress_loops = 0
        last_updated_count = 0
        last_create_count = 0
        while not task_finished:
            try:
                task = self.es.tasks.list(task_id=task_id, params={"detailed": True})["nodes"][node_id]["tasks"][task_id]
                status = task["status"]
                print("Updated/Created/Total: ", status["updated"], status["created"], status["total"])
                if last_updated_count != status["updated"] or last_create_count != status["created"]:
                    last_updated_count = status["updated"]
                    last_create_count = status["created"]
                    # reset progress
                    no_progress_loops = 0
                else:
                    no_progress_loops += 1
                if no_progress_loops == 10:
                    self.es.tasks.cancel(task_id=task_id)
                    self.cancelled_queries.append(query)
                    raise Exception("Cancelling task that didn't progress in last 1.6mins {}".format(str(query)))
                running_time_in_mins = (task["running_time_in_nanos"] / 60000000000)
                print("Running time total in mins ", running_time_in_mins)
            except Exception as e:
                task_finished = True
                print(e)
                print("This could mean task finished succesfully")
                return
            time.sleep(20)

    def _range_query(self, start_date, end_date):
        def format_date(date):
            if isinstance(date, str):
                return date
            else:
                return date.strftime('%Y-%m-%d')

        return {
            "query": {
                "range": {
                    "inserted_at": {
                        "gte": format_date(start_date),
                        "lte": format_date(end_date),
                        "format": 'yyyy-MM-dd'
                    }
                }
            },
        }

    def get_es7_count(self, start_date=None, end_date=None):
        self.es.indices.refresh(self.index)
        query = self._range_query(start_date, end_date) if start_date and end_date else None
        ret = self.es.count(index=self.index, body=query)
        return ret["count"]

    def get_es2_count(self, start_date=None, end_date=None):
        url = '{host}/{index}/{type}/_count'.format(
            host=self.es2_remote_host,
            index=self.index,
            type=self.index_info.type
        )
        if start_date and end_date:
            q = json.dumps(self._range_query(start_date, end_date))
            response = requests.get(url, data=q, headers={'content-type':'application/json'})
        else:
            response = requests.get(url)
        if response.status_code != 200:
            raise Exception("Error getting document counts from remote cluster")
        else:
            response = json.loads(response.text)
            return response.get('count')
