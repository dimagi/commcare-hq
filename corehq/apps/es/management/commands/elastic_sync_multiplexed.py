import math
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.es.client import (
    BulkActionItem,
    ElasticMultiplexAdapter,
    Tombstone,
    get_client,
)
from corehq.apps.es.registry import get_registry
from corehq.apps.es.transient_util import _DOC_ADAPTERS_BY_INDEX
from corehq.apps.hqcase.management.commands.reindex_es_native import (
    check_task_progress,
)


class ESSyncUtil:

    """
    This class contains methods to support the reindex process of multiplexed indices in HQ
    """

    def __init__(self):
        self.es = get_client()

    def start_reindex(self, cname):

        self.adapter = self.get_adapter(cname)

        if not isinstance(self.adapter, ElasticMultiplexAdapter):
            raise IndexNotMultiplexedException("""Index not multiplexed!
            Sync can only be run on multiplexed indices""")

        self.source, self.dest = self.get_source_destination_indexes(self.adapter)

        result_info = self.start_reindex_in_es(self.source, self.dest)

        task_id = result_info["task"]

        # This would display progress untill reindex process is completed
        check_task_progress(self.es, task_id)

        self.perform_cleanup()

    def get_adapter(self, cname):
        index_name = get_registry()[cname].index
        return _DOC_ADAPTERS_BY_INDEX[index_name]

    def get_source_destination_indexes(self, adapter):
        return adapter.primary.index_name, adapter.secondary.index_name

    def perform_cleanup(self):
        print("\n\tPerforming Cleanup:")

        print("\nDeleting Tombstones")
        self.delete_tombstones(self.adapter.secondary)

        print("\nMarking Index eligible to upgrade to primary")
        self.mark_primary_eligible()

    def mark_primary_eligible(self):
        # Would be used to mark the secondary index eligible to be primary.
        # This would be implemented when supporting models are created.
        pass

    def delete_tombstones(self, secondary_adapter):
        # This should be replaced by delete_by_query
        # https://www.elastic.co/guide/en/elasticsearch/reference/5.1/docs-delete-by-query.html
        # when on ES version >= 5
        tombstone_ids = self._get_tombstone_ids(secondary_adapter)
        actions = [BulkActionItem.delete_id(doc_id=t_id)
        for t_id in tombstone_ids]
        secondary_adapter.bulk(actions, refresh=True)

    def _get_tombstone_ids(self, secondary_adapter):
        query = {
            "query": {
                "bool": {
                    "must": {
                        "match": {
                            Tombstone.PROPERTY_NAME: True
                        }
                    }
                }
            },
            "_source": False,
        }
        scroll_iter = secondary_adapter.scroll(query, size=1000)
        tombstone_ids = [doc['_id'] for doc in scroll_iter]
        return tombstone_ids

    def start_reindex_in_es(self, source, dest):
        # https://www.elastic.co/guide/en/elasticsearch/reference/2.4/docs-reindex.html
        reindex_body = {
            "source": {
                "index": source,
            },
            "dest": {
                "index": dest,
                "op_type": "create",
                "version_type": "external"
            },
            "conflicts": "proceed"
        }
        task_id = self.es.reindex(reindex_body, wait_for_completion=False)
        return task_id

    def cancel_reindex(self, task_id):
        result = self.es.tasks.cancel(task_id)
        node_failures = result.get('node_failure', None)
        if node_failures:
            raise CommandError(f"No Reindes process with {task_id} found")
        node_id = task_id.split(':')[0]
        task_info = result['nodes'][node_id]['tasks'][task_id]

        start_time = datetime.utcfromtimestamp(task_info['start_time_in_millis'] / 1000)
        running_duration_seconds = task_info['running_time_in_nanos'] / 10**9
        duration = human_readable_seconds(running_duration_seconds)

        print(f"Reindex task {task_id} cancelled!")
        print(f"Task was started at {start_time} and ran for {duration}")

    def reindex_status(self, task_id):
        check_task_progress(self.es, task_id)


def human_readable_seconds(duration):
    """
    :param duration int: Duration in seconds
    :returns a formatted string with correct time unit
    """
    seconds_in_minute = 60
    seconds_in_hour = 60 * seconds_in_minute
    seconds_in_day = 24 * seconds_in_hour

    if duration < seconds_in_minute:
        duration = math.floor(duration)
        return f"{duration} seconds"
    if duration < seconds_in_hour:
        duration = math.floor(duration / seconds_in_minute)
        return f"{duration} minutes"
    if duration < seconds_in_day:
        duration = math.floor(duration / seconds_in_hour)
        return f"{duration} hours"
    else:
        duration = math.floor(duration / seconds_in_day)
        return f"{duration} days"


class Command(BaseCommand):
    """
    ES sync management command. It can be used to manage reindex processes on HQ indices.
    The command requires the index to be multiplexed before the reindex is started.
    This management command currently supports three subcommands

    ```bash
    ./manage.py elastic_sync_multiplexed start <index_cname>
    ```
    <index_cname> is the hq cannoical name for an index like forms, cases

    ```bash
    ./manage.py elastic_sync_multiplexed cancel <task_id>
    ```

    ```bash
    ./manage.py elastic_sync_multiplexed status <task_id>
    ```

    <task_id> is the reindex operation id that would be printed by start command

    """

    help = ("Reindex management command to sync Multiplexed HQ indices")

    es_helper = ESSyncUtil()

    def add_arguments(self, parser):

        INDEXES = list(get_registry().keys())

        # Setup subparsers
        subparsers = parser.add_subparsers(required=True, dest="sub_command")

        # Start Reindex Process
        start_cmd = subparsers.add_parser("start")
        start_cmd.set_defaults(func=self.es_helper.start_reindex)
        start_cmd.add_argument(
            'index_cname',
            choices=INDEXES,
            help="""Cannonical Name of the index that need to be synced""",
        )

        # Get ReIndex Process Status
        status_cmd = subparsers.add_parser("status")
        status_cmd.set_defaults(func=self.es_helper.reindex_status)
        status_cmd.add_argument(
            "task_id",
            help="""Check the status of active reindex process.
            """
        )

        # Cancel Reindex Process
        cancel_cmd = subparsers.add_parser("cancel")
        cancel_cmd.set_defaults(func=self.es_helper.cancel_reindex)
        cancel_cmd.add_argument(
            "task_id",
            help="""Cancels an ongoing reindex process""",
        )

    def handle(self, **options):
        sub_cmd = options['sub_command']
        cmd_func = options.get('func')
        if sub_cmd == 'start':
            cmd_func(options['index_cname'])
        else:
            cmd_func(options['task_id'])


class IndexNotMultiplexedException(Exception):
    pass
