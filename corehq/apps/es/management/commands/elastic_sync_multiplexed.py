import logging
import time
from datetime import datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from corehq.apps.es.client import ElasticMultiplexAdapter, get_client
from corehq.apps.es.client import manager as es_manager
from corehq.apps.es.exceptions import IndexNotMultiplexedException, TaskMissing
from corehq.apps.es.index.settings import render_index_tuning_settings
from corehq.apps.es.transient_util import (
    doc_adapter_from_cname,
    iter_index_cnames,
)
from corehq.apps.es.utils import check_task_progress

logger = logging.getLogger('elastic_sync_multiplexed')


class ESSyncUtil:

    """
    This class contains methods to support the reindex process of multiplexed indices in HQ.

    ** NOTE ** If this util is used somewhere else in future it should be moved to ES utils
    rather than importing it from this management command.
    """

    def __init__(self):
        self.es = get_client()

    def start_reindex(self, cname):

        adapter = doc_adapter_from_cname(cname)

        if not isinstance(adapter, ElasticMultiplexAdapter):
            raise IndexNotMultiplexedException("""Index not multiplexed!
            Sync can only be run on multiplexed indices""")

        source_index, destination_index = self._get_source_destination_indexes(adapter)

        logger.info(f"Preparing index {destination_index} for reindex")
        self._prepare_index_for_reindex(destination_index)

        logger.info("Starting ReIndex process")
        task_info = es_manager.reindex(source_index, destination_index)
        logger.info(f"Copying docs from index {source_index} to index {destination_index}")
        task_id = task_info.split(':')[1]
        print("\n\n\n")
        logger.info("-----------------IMPORTANT-----------------")
        logger.info(f"TASK ID - {task_id}")
        logger.info("-------------------------------------------")
        logger.info("Save this Task Id, You will need it later for verifying your reindex process")
        print("\n\n\n")
        # This would display progress untill reindex process is completed
        check_task_progress(task_info)

        print("\n\n")
        self.perform_cleanup(adapter)

        logger.info("Preparing Index for normal use")
        self._prepare_index_for_normal_usage(adapter.secondary)
        print("\n\n")

        self._get_source_destination_doc_count(adapter)

        logger.info(f"Verify this reindex process from elasticsearch logs using task id - {task_id}")
        print("\n\n")
        logger.info("You can use commcare-cloud to extract reindex logs from cluster")
        print("\n\t"
            + f"cchq {settings.SERVER_ENVIRONMENT} run-shell-command elasticsearch "
            + f"\"grep '{task_id}.*ReindexResponse' opt/data/elasticsearch*/logs/*es.log\""
            + "\n\n")

    def _get_source_destination_indexes(self, adapter):
        return adapter.primary.index_name, adapter.secondary.index_name

    def _prepare_index_for_reindex(self, index_name):
        es_manager.cluster_routing(enabled=True)
        es_manager.index_configure_for_reindex(index_name)
        es_manager.index_set_replicas(index_name, 0)
        self._wait_for_index_to_get_healthy(index_name, sleep_time=5)
        es_manager.cluster_routing(enabled=False)

    def _wait_for_index_to_get_healthy(self, index_name, sleep_time=0):
        for i in range(10):
            health = es_manager.cluster_health(index=index_name)
            status = health["status"]
            if status == "green":
                break

            print(f"\tWaiting for index status to be green. Current status: '{status}'")
            time.sleep(sleep_time)

    def _prepare_index_for_normal_usage(self, secondary_adapter):
        es_manager.cluster_routing(enabled=True)
        tuning_settings = render_index_tuning_settings(secondary_adapter.settings_key)
        es_manager.index_set_replicas(secondary_adapter.index_name, tuning_settings['number_of_replicas'])
        es_manager.index_configure_for_standard_ops(secondary_adapter.index_name)
        self._wait_for_index_to_get_healthy(secondary_adapter.index_name, sleep_time=5)
        es_manager.cluster_routing(enabled=True)

    def _get_source_destination_doc_count(self, adapter):
        es_manager.index_refresh(adapter.primary.index_name)
        es_manager.index_refresh(adapter.secondary.index_name)
        primary_count = adapter.count({})
        secondary_count = adapter.secondary.count({})
        print(f"Doc Count In Old Index '{adapter.primary.index_name}' - {primary_count}")
        print(f"Doc Count In New Index '{adapter.secondary.index_name}' - {secondary_count}\n\n")

    def perform_cleanup(self, adapter):
        logger.info("Performing required cleanup!")
        logger.info("Deleting Tombstones")
        adapter.secondary.delete_tombstones()

    def cancel_reindex(self, task_id):
        try:
            task_info = es_manager.cancel_task(task_id)
        except TaskMissing:
            raise CommandError(f"No Reindex process with {task_id} found")

        start_time = datetime.utcfromtimestamp(task_info['start_time_in_millis'] / 1000)
        running_duration_seconds = task_info['running_time_in_nanos'] / 10**9
        duration = timedelta(running_duration_seconds)

        logger.info(f"Reindex task {task_id} cancelled!")
        logger.info(f"Task was started at {start_time} and ran for {duration}")

    def reindex_status(self, task_id):
        check_task_progress(task_id, just_once=True)


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

        INDEXES = list(iter_index_cnames())

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
