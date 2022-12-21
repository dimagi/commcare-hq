import inspect
import time

from django.core.management.base import BaseCommand, CommandError
from corehq.apps.es.utils import check_task_progress

from pillowtop.es_utils import initialize_index, set_index_reindex_settings

from corehq.apps.es.client import manager
from corehq.apps.es.transient_util import (
    index_info_from_cname,
    iter_index_cnames,
)
from corehq.elastic import get_es_export

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
            "target_index_name", choices=list(iter_index_cnames()),
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

        target_index_info = index_info_from_cname(target_index_name)
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

    result = manager.reindex(reindex_query, wait_for_completion=False)
    task_id = result["task"]
    return task_id


def _get_doc_count(es, index):
    es.indices.refresh(index)
    return es.indices.stats(index=index)['indices'][index]['primaries']['docs']['count']
