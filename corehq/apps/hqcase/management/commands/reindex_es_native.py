import inspect
import time
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError

from corehq.elastic import get_es_export, ES_META
from pillowtop.es_utils import initialize_index, set_index_reindex_settings

USAGE = """Reindex data from one ES index into another ES index using Elasticsearch reindex API
    https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-reindex.html#reindex-from-remote.
"""


class Command(BaseCommand):
    help = USAGE

    def add_arguments(self, parser):
        parser.add_argument(
            "source_index",
            help="Index to be used as the source",
        )
        parser.add_argument(
            "target_index", choices=ES_META,
            help="Index to be used as the target"
        )
        parser.add_argument(
            "--print_index_size",
            action="store_true",
            default=False,
            help="Print number of docs in source and target index"
        )
        parser.add_argument(
            "--monitor-task-id",
            help="Pass in the task ID of an existing reindex to monitor it's progress. This will not kick off"
                 "a new reindex."
        )

    def handle(self, source_index, target_index, **options):
        es = get_es_export()
        if not es.indices.exists(source_index):
            raise CommandError(f"Source index does not exist: '{source_index}'")

        target_index_info = ES_META[target_index]
        target_index = target_index_info.index
        _initialize_target(es, target_index_info)

        source_count = _get_doc_count(es, source_index)
        target_count = _get_doc_count(es, target_index)
        print("Number of docs in source index", source_count)
        print("Number of docs in target index", target_count)

        if options.get("print_index_size"):
            return

        elif source_count == target_count:
            print("Doc counts are same, nothing left to reindex. Exiting!")
            return

        if not options["monitor_task_id"]:
            print(f"Starting reindex for index from '{source_index}' to '{target_index}'")
            task_id = start_reindex(es, source_index, target_index)
        else:
            task_id = options["monitor_task_id"]
        check_task_progress(es, task_id)

        print(inspect.cleandoc(f"""
            If you would like to check, you may run this
            command again with --print_index_size to make sure
            doc counts match across both indices.

            Once you are satisfied that the reindex is complete you should run the following:

            ./manage.py initialize_es_indices --index {target_index} --set-for-usage
        """))


def _initialize_target(es, target_index_info):
    if es.indices.exists(target_index_info.index):
        print(f"Target index '{target_index_info.index}' already exists. Skipping initialization.")
        return

    print("Creating target index")
    initialize_index(es, target_index_info)
    set_index_reindex_settings(es, target_index_info.index)

    print("Setting number of replicas to 0")
    es.indices.put_settings({
        "index.number_of_replicas": 0
    }, index=target_index_info.index)


def start_reindex(es, source_index, target_index):
    reindex_query = {
        "source": {
            "index": source_index,
        },
        "dest": {
            "index": target_index
        },
        "conflicts": "proceed"
    }

    result = es.reindex(reindex_query, wait_for_completion=False, request_timeout=300)
    task_id = result["task"]
    return task_id


def check_task_progress(es, task_id):
    node_id = task_id.split(':')[0]
    node_name = es.nodes.info(node_id, metric="name")["nodes"][node_id]["name"]
    print(f"Task with ID '{task_id}' running on '{node_name}'")
    while True:
        result = es.tasks.list(task_id=task_id, detailed=True)
        if not result["nodes"]:
            node_failure = result["node_failures"][0]
            error = node_failure["caused_by"]["type"]
            if error == "resource_not_found_exception":
                print("Reindex task complete or failed. Please check ES logs for final output.")
                return
            else:
                raise CommandError(f"Fetching task failed: {node_failure}")

        task_details = result["nodes"][node_id]["tasks"][task_id]
        status = task_details["status"]
        total = status["total"]
        if total:  # total can be 0 initially
            created, updated, deleted = status["created"], status["updated"], status["deleted"]
            progress = created + updated + deleted
            progress_percent = progress / total * 100

            running_time_nanos = task_details["running_time_in_nanos"]
            run_time = timedelta(microseconds=running_time_nanos / 1000)

            remaining_time = 'unknown'
            if progress:
                remaining = total - progress
                remaining_nanos = running_time_nanos / progress * remaining
                remaining_time = timedelta(microseconds=remaining_nanos / 1000)

            print(f"Progress {progress_percent:.2f}% ({progress} / {total}). "
                  f"Elapsed time: {run_time}. "
                  f"Estimated remaining time: {remaining_time}")

        time.sleep(5)


def _get_doc_count(es, index):
    es.indices.refresh(index)
    return es.indices.stats(index=index)['indices'][index]['primaries']['docs']['count']
