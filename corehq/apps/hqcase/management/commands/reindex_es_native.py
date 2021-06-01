import inspect
import time
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from elasticsearch import NotFoundError

from corehq.elastic import get_es_export, ES_META
from pillowtop.reindexer.reindexer import prepare_index_for_reindex

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

        print(f"Starting reindex for index from '{source_index}' to '{target_index}'")
        reindex_and_poll_progress(es, source_index, target_index)

        print(inspect.cleandoc(f"""
            If you would like to check, you may run this
            command again with --print_index_size to make sure
            doc counts match across both indices.

            Once you are satisfied that the reindex is complete you should run the following:

            ./manage.py initialize_es_indices --index {target_index} --set-for-usage
        """))


def _initialize_target(es, target_index_info):
    if not es.indices.exists(target_index_info.index):
        try:
            alias = es.indices.get_alias(target_index_info.alias)
        except NotFoundError:
            pass
        else:
            raise CommandError(f"Target index alias is already assigned to {','.join(list(alias))}")

        print("Creating target index")
        prepare_index_for_reindex(es, target_index_info)

        print("Setting number of replicas to 0")
        es.indices.put_settings({
            "number_of_replicas": 0
        }, index=target_index_info.index)


def reindex_and_poll_progress(es, source_index, target_index):
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
        created, updated, deleted = status["created"], status["updated"], status["deleted"]
        progress = created + updated + deleted
        progress_percent = progress / total * 100

        running_time_nanos = task_details["running_time_in_nanos"]
        run_time = timedelta(microseconds=running_time_nanos / 1000)

        print(f"Progress {progress_percent:.2f}% ({progress} / {total}). Duration: {run_time}")

        time.sleep(5)


def _get_doc_count(es, index):
    es.indices.refresh(index)
    return es.indices.stats(index=index)['indices'][index]['primaries']['docs']['count']
