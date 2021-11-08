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
            "target_index_name", choices=ES_META,
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

    def handle(self, source_index, target_index_name, **options):
        es = get_es_export()
        if not es.indices.exists(source_index):
            raise CommandError(f"Source index does not exist: '{source_index}'")

        target_index_info = ES_META[target_index_name]
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

        print("\nReindex task complete.")
        source_count = _get_doc_count(es, source_index)
        target_count = _get_doc_count(es, target_index)
        print("Number of docs in source index", source_count)
        print("Number of docs in target index", target_count)

        print("")
        print(inspect.cleandoc(f"""
            Perform manual checks to verify the reindex is complete.
            Once you are satisfied that the reindex is complete you should run the following:

            ./manage.py initialize_es_indices --index {target_index_name} --set-for-usage
        """))


def _initialize_target(es, target_index_info):
    if es.indices.exists(target_index_info.index):
        print(f"Target index '{target_index_info.index}' already exists. Skipping initialization.")
        return

    print("Creating target index")

    print("\tEnabling cluster routing")
    es.cluster.put_settings({"transient": {"cluster.routing.allocation.enable": "all"}})

    initialize_index(es, target_index_info)
    set_index_reindex_settings(es, target_index_info.index)

    print("\tSetting number of replicas to 0")
    es.indices.put_settings({
        "index.number_of_replicas": 0
    }, index=target_index_info.index)

    for i in range(6):
        health = es.cluster.health(index=target_index_info.index)
        status = health["status"]
        if status == "green":
            break

        print(f"\tWaiting for index status to be green. Current status: '{status}'")
        time.sleep(5)

    print("\tDisabling cluster routing")
    es.cluster.put_settings({"transient": {"cluster.routing.allocation.enable": "none"}})


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
    progress_data = []
    while True:
        result = es.tasks.list(task_id=task_id, detailed=True)
        if not result["nodes"]:
            node_failure = result["node_failures"][0]
            error = node_failure["caused_by"]["type"]
            if error == "resource_not_found_exception":
                return  # task completed
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

            remaining_time_absolute = 'unknown'
            remaining_time_relative = ''
            if progress:
                progress_data.append({
                    "progress": progress,
                    "time": time.monotonic() * 1000000000
                })

                remaining = total - progress
                # estimate based on progress since beginning of task
                remaining_nanos_absolute = running_time_nanos / progress * remaining
                remaining_time_absolute = timedelta(microseconds=remaining_nanos_absolute / 1000)
                if len(progress_data) > 1:
                    # estimate based on last 12 loops of data
                    progress_nanos = progress_data[-1]["time"] - progress_data[0]["time"]
                    progress_diff = progress_data[-1]["progress"] - progress_data[0]["progress"]
                    progress_data = progress_data[-12:]  # truncate progress data
                    remaining_nanos = progress_nanos / progress_diff * remaining
                    remaining_time_relative = timedelta(microseconds=remaining_nanos / 1000)

            print(f"Progress {progress_percent:.2f}% ({progress} / {total}). "
                  f"Elapsed time: {_format_timedelta(run_time)}. "
                  f"Estimated remaining time: "
                  f"(average since start = {_format_timedelta(remaining_time_absolute)}) "
                  f"(recent average = {_format_timedelta(remaining_time_relative)})")

        time.sleep(10)


def _get_doc_count(es, index):
    es.indices.refresh(index)
    return es.indices.stats(index=index)['indices'][index]['primaries']['docs']['count']


def _format_timedelta(td):
    out = str(td)
    return out.split(".")[0]
