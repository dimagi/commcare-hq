import json
import requests
import time
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError

from corehq.elastic import get_es_export, ES_META


USAGE = """Reindex data into local Elasticsearch v7 cluster from remote
    Elasticsearch v2 cluster using Elasticsearch reindex API
    https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-reindex.html#reindex-from-remote.

    To use this command to reindex data, make sure that
    - The localsettings from where this command points to Elasticsearch7 host and port
    - The Elasticsearch 7 cluster has the remote host whitelisted by having the
      elasticsearch setting `reindex.remote.whitelist` set to remote es2 host in elasticsearch.yml
    - The relevant index must be initialized using initialize_es_indices management command
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
            help="Remote ES2 host in http://otherhost:port format"
        )
        parser.add_argument(
            "--start_date",
            default=None,
            help="start date (inclusive) to reindex docs based on inserted_at field."
                 "This is supported only for Form and Case indices. "
                 "In yyyy-MM-dd format. Providing the date range makes reindex run day by day"
        )
        parser.add_argument(
            "--end_date",
            default=None,
            help="end date (inclusive) to reindex docs based on inserted_at field."
                 "This is supported only for Form and Case indices. "
                 "In yyyy-MM-dd format. Providing the date range makes reindex run day by day"
        )
        parser.add_argument(
            "--batch_size",
            default=1000,
            type=int,
            help="Batch size used by Elasticsearch reindex (default 1000)"
        )
        parser.add_argument(
            "--print_index_size",
            action="store_true",
            default=False,
            help="Print number of docs in remote and new cluster"
        )

    def handle(self, index_name, es2_remote_host, **options):
        assert index_name in ES_META, "Index name should be one of " + str(ES_META.keys())
        self.options = options
        self.index_info = ES_META[index_name]
        self.index = self.index_info.index
        self.es2_remote_host = es2_remote_host
        # Cancelled/failed reindex queries are tracked to be retried
        self.cancelled_queries = []
        self.es = get_es_export()
        if index_name not in ["forms", "cases"] and (options.get('start_date') or options.get('end_date')):
            raise CommandError("start and end dates are supported only for form/case indices")
        elif index_name in ["forms", "cases"]:
            start_date = options.get('start_date')
            end_date = options.get('end_date')
        else:
            start_date, end_date = None, None
        local_count = self.get_es7_count(start_date, end_date)
        remote_count = self.get_es2_count(start_date, end_date)
        print("Number of docs in remote ES2 index", remote_count)
        print("Number of docs in local ES7 index", local_count, "\n")

        if options.get("print_index_size"):
            return
        elif local_count == remote_count:
            print("Doc counts are same, nothing left to reindex. Exiting!")
            return
        else:
            self.reindex(start_date, end_date)

    def reindex(self, start_date=None, end_date=None):
        start_date = datetime.strptime(start_date, '%Y-%m-%d') if start_date else None
        end_date = datetime.strptime(end_date, '%Y-%m-%d') if end_date else None

        reindex_query = {
            "source": {
                "remote": {
                    "host": self.es2_remote_host
                },
                "index": self.index,
                "size": self.options.get('batch_size', 1000),
                "_source": {"exclude": ["_id"]}
            },
            "dest": {"index": self.index},
            "conflicts": "proceed"
        }

        if start_date and end_date:
            days = (end_date - start_date).days
            for start in (start_date + timedelta(days=n) for n in range(days + 1)):
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
            if start_date or end_date:
                reindex_query["source"].update(self._range_query(start_date, end_date))
            print("Starting reindex for index {i}".format(i=self.index))
            self.reindex_and_poll_progress(reindex_query)
        if self.cancelled_queries:
            confirm = input(
                """
                There were {} reindex tasks that didn't finish, would you like
                to retry these (y/N)?
                """.format(len(self.cancelled_queries))
            )
            if confirm == "y":
                for query in self.cancelled_queries:
                    self.reindex_and_poll_progress(query)
        print("""
            Reindex finished, exiting!
            If you would like to check, you may run this
            command again with --print_index_size to make sure
            doc counts match across both indices.
        """)

    def reindex_and_poll_progress(self, reindex_query):
        # Initialize reindex and poll the reindex status using the tasks API
        # Cancels the queries if the reindex is stuck for any reason and tracks it
        # under self.cancelled_queries to be prompted for retry
        print("Running reindex query ", reindex_query)
        result = self.es.reindex(reindex_query, wait_for_completion=False, request_timeout=300)
        print("Reindex is in progress, task id is ", result, "Progress is displayed every 5 seconds")
        task_id = result["task"]
        running_time = -1
        no_progress_loops = 0
        last_updated_count = 0
        last_create_count = 0
        completed = False
        while not completed:
            result = self.es.tasks.get(task_id=task_id)
            completed = result.get('completed', False)
            task = result["task"]
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
                self.cancelled_queries.append(reindex_query)
                print("Cancelling task that didn't progress in last 10 polls {}".format(str(query)))
            running_time = task["running_time_in_nanos"]
            running_time_in_mins = (running_time / 60000000000)
            print("Running time total in mins so far", running_time_in_mins, "\n")
            time.sleep(5)
        print("Current reindex task is finished")

    def _range_query(self, start_date, end_date):
        def format_date(date):
            if isinstance(date, str):
                return date
            else:
                return date.strftime('%Y-%m-%d')

        range_kwargs = {"format": 'yyyy-MM-dd'}
        if start_date:
            range_kwargs["gte"] = format_date(start_date)
        if end_date:
            range_kwargs["lte"] = format_date(end_date)

        return {
            "query": {
                "range": {
                    "inserted_at": range_kwargs
                }
            },
        }

    def get_es7_count(self, start_date=None, end_date=None):
        self.es.indices.refresh(self.index)
        query = self._range_query(start_date, end_date) if start_date or end_date else None
        ret = self.es.count(index=self.index, body=query)
        return ret["count"]

    def get_es2_count(self, start_date=None, end_date=None):
        url = f'{self.es2_remote_host}/{self.index}/{self.index_info.type}/_count'
        if start_date or end_date:
            q = json.dumps(self._range_query(start_date, end_date))
            response = requests.get(url, data=q, headers={'content-type': 'application/json'})
        else:
            response = requests.get(url)
        if response.status_code != 200:
            raise Exception("Error getting document counts from remote cluster")
        else:
            response = json.loads(response.text)
            return response.get('count')
