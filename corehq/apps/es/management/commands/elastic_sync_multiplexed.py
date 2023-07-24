import logging
import time
from datetime import datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from corehq.apps.es import CANONICAL_NAME_ADAPTER_MAP

import corehq.apps.es.const as es_consts
from corehq.apps.es.client import ElasticMultiplexAdapter, get_client
from corehq.apps.es.client import manager as es_manager
from corehq.apps.es.exceptions import (
    IndexAlreadySwappedException,
    IndexMultiplexedException,
    IndexNotMultiplexedException,
    TaskMissing,
)
from corehq.apps.es.index.settings import render_index_tuning_settings
from corehq.apps.es.transient_util import (
    doc_adapter_from_cname,
    iter_index_cnames,
)
from corehq.apps.es.utils import check_task_progress
from corehq.util.markup import SimpleTableWriter, TableRowFormatter
from pillowtop.checkpoints.manager import KafkaPillowCheckpoint
from pillowtop.utils import get_all_pillow_instances

logger = logging.getLogger('elastic_sync_multiplexed')


class ESSyncUtil:

    """
    This class contains methods to support the reindex process of multiplexed indices in HQ.

    ** NOTE ** If this util is used somewhere else in future it should be moved to ES utils
    rather than importing it from this management command.
    """

    def __init__(self):
        self.es = get_client()

    def start_reindex(self, cname, reindex_batch_size=1000,
                      purge_ids=False, requests_per_second=None, with_no_replicas=False):

        adapter = doc_adapter_from_cname(cname)

        if not isinstance(adapter, ElasticMultiplexAdapter):
            raise IndexNotMultiplexedException("""Index not multiplexed!
            Sync can only be run on multiplexed indices""")

        source_index, destination_index = self._get_source_destination_indexes(adapter)

        logger.info(f"Preparing index {destination_index} for reindex")
        self._prepare_index_for_reindex(destination_index)

        logger.info("Starting ReIndex process")
        task_info = es_manager.reindex(
            source_index, destination_index,
            batch_size=reindex_batch_size, purge_ids=purge_ids,
            requests_per_second=requests_per_second
        )
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

        if not with_no_replicas:
            logger.info("Preparing Index for normal use")
            self._prepare_index_for_normal_usage(adapter.secondary)
            print("\n\n")
        else:
            logger.info(f"Replicas are not being set for index {destination_index}")
            logger.info("You can manually set them by running")
            print("\n\n")
            print(f"\t./manage.py elastic_sync_multiplexed set_replicas {cname}")
            print("\n\n")

        self._get_source_destination_doc_count(adapter)

        logger.info(f"Verify this reindex process from elasticsearch logs using task id - {task_id}")
        print("\n\n")
        logger.info("You can use commcare-cloud to extract reindex logs from cluster")
        print("\n\t"
            + f"cchq {settings.SERVER_ENVIRONMENT} run-shell-command elasticsearch "
            + f"\"grep '{task_id}.*ReindexResponse' /opt/data/elasticsearch*/logs/*.log\""
            + "\n\n")

    def _get_source_destination_indexes(self, adapter):
        return adapter.primary.index_name, adapter.secondary.index_name

    def _prepare_index_for_reindex(self, index_name):
        es_manager.cluster_routing(enabled=True)
        es_manager.index_configure_for_reindex(index_name)
        es_manager.index_set_replicas(index_name, 0)
        self._wait_for_index_to_get_healthy(index_name)
        es_manager.cluster_routing(enabled=False)

    def _wait_for_index_to_get_healthy(self, index_name):
        for i in range(10):
            health = es_manager.cluster_health(index=index_name)
            status = health["status"]
            if status == "green":
                break

            print(f"\tWaiting for index status to be green. Current status: '{status}'")
            time.sleep(min(2 ** i, 30))

    def _prepare_index_for_normal_usage(self, secondary_adapter):
        es_manager.cluster_routing(enabled=True)
        tuning_settings = render_index_tuning_settings(secondary_adapter.settings_key)
        logger.info(f"Setting replica count to {tuning_settings['number_of_replicas']}")
        es_manager.index_set_replicas(secondary_adapter.index_name, tuning_settings['number_of_replicas'])
        es_manager.index_configure_for_standard_ops(secondary_adapter.index_name)
        self._wait_for_index_to_get_healthy(secondary_adapter.index_name)
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
        if isinstance(adapter, ElasticMultiplexAdapter):
            logger.info("Deleting Tombstones From Secondary Index")
            adapter.secondary.delete_tombstones()
        else:
            logger.info("Deleting Tombstones From Primary Index")
            adapter.delete_tombstones()

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

    def delete_index(self, cname):
        """Deletes the older index after reindexing

        This should be used during the reindex process to delete the older index.
        The function assumes that reindex process is successful, multiplexes is turned off
        and indexes have been swapped.

        """
        adapter = doc_adapter_from_cname(cname)
        current_index, older_index = self._get_current_and_older_index_name(cname)
        if isinstance(adapter, ElasticMultiplexAdapter):
            raise IndexMultiplexedException(f"""A multiplexed index cannot be deleted.
            Make sure you have set ES_{cname.upper()}_INDEX_MULTIPLEXED to False """)

        assert adapter.index_name == current_index, f"""Indexes not swapped yet.
        Make sure after reindexing set ES_{cname.upper()}_INDEX_SWAPPED to True"""

        older_doc_adapter = adapter.__class__(older_index, adapter.type)

        older_index_count = older_doc_adapter.count({})
        newer_index_count = adapter.count({})

        print(f"Docs in older index - {older_index_count}")
        print(f"Docs in newer index - {newer_index_count}")

        print("\nDocs in new index should be greater than or equals to in older index")

        print(f"Are you sure you want to delete the older index - {older_index}?")
        print("WARNING: - This step can't be un-done.")
        user_confirmation = input(f"Enter '{cname}' to continue, any other key to cancel\n")
        if user_confirmation != cname:
            raise CommandError("Exiting Index Deletion Process")
        print(f"Deleting Index - {older_index}")

        es_manager.index_delete(older_index)

    def _get_current_and_older_index_name(cls, cname):
        """
        Returns a tuple of current index name and older index name related to the given cname.
        Older index refers to the source index during reindex process
        Current index refers to the destination index
        """
        current_index = getattr(es_consts, f"HQ_{cname.upper()}_SECONDARY_INDEX_NAME")
        older_index = getattr(es_consts, f"HQ_{cname.upper()}_INDEX_NAME")
        return (current_index, older_index)

    def set_checkpoints_for_new_index(self, cname):
        """
        Takes in an index cname and create new checkpoint for all the pillows that use the older index name
        for that cname.
        Can only be performed when indexes are still multiplexed and not swapped.
        When we swap the indexes, the primary index changes which updates the checkpoint names.
        We should stop the pillows and copy the checkpoint to the new checkpoint ids, swap the indexes
        and then start the pillows.
        """
        adapter = doc_adapter_from_cname(cname)
        if not isinstance(adapter, ElasticMultiplexAdapter):
            raise IndexNotMultiplexedException(f"""Checkpoints can be copied on multiplexed indexes.
                Make sure you have set ES_{cname.upper()}_INDEX_MULTIPLEXED to True """)

        current_index_name, older_index_name = self._get_current_and_older_index_name(cname)

        if getattr(settings, f'ES_{cname.upper()}_INDEX_SWAPPED'):
            raise IndexAlreadySwappedException(
                f"""Checkpoints can only be copied before swapping indexes.
                Make sure you have set ES_{cname.upper()}_INDEX_SWAPPED to False."""
            )

        all_pillows = get_all_pillow_instances()
        for pillow in all_pillows:
            old_checkpoint_id = pillow.checkpoint.checkpoint_id
            if older_index_name in old_checkpoint_id:
                new_checkpoint_id = old_checkpoint_id.replace(older_index_name, current_index_name)
                print(f"Copying checkpoints of Checkpoint ID -  [{old_checkpoint_id}] to [{new_checkpoint_id}]")
                self._copy_checkpoints(pillow, new_checkpoint_id)

    def _copy_checkpoints(self, pillow, new_checkpoint_id):
        last_known_checkpoint = pillow.checkpoint.get_current_sequence_as_dict()
        new_checkpoint = KafkaPillowCheckpoint(new_checkpoint_id, topics=pillow.topics)
        new_checkpoint.update_to(last_known_checkpoint)

    def estimate_disk_space_for_reindex(self, stdout=None):
        indices_info = es_manager.indices_info()
        index_cname_map = self._get_index_name_cname_map()
        index_size_rows = []
        total_size = 0
        for index_name in index_cname_map.keys():
            meta = indices_info[index_name]
            index_size_rows.append([
                index_cname_map[index_name],
                index_name,
                self._format_bytes(int(meta['size_on_disk'])),
                meta['doc_count']
            ])
            total_size += int(meta['size_on_disk'])
        self._print_table(index_size_rows, output=stdout)
        recommended_disk = self._format_bytes(total_size * 1.2)  # 20% more that what is used
        print("\n\n")
        print(f"Minimum free disk space recommended before starting the reindex: {recommended_disk}")

    def _get_index_name_cname_map(self):
        return {adapter.index_name: cname for cname, adapter in CANONICAL_NAME_ADAPTER_MAP.items()}

    def _format_bytes(self, size):
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        index = 0

        while size >= 1024 and index < len(units) - 1:
            size /= 1024
            index += 1
        return '{:.2f} {}'.format(size, units[index])

    def _print_table(self, rows, output):
        row_formatter = TableRowFormatter(
            [20, 30, 20, 30]
        )
        SimpleTableWriter(output=output, row_formatter=row_formatter).write_table(
            ["Index CName", "Index Name", "Size on Disk", "Doc Count"], rows=rows
        )

    def set_replicas_for_secondary_index(self, cname):
        adapter = doc_adapter_from_cname(cname)

        if not getattr(settings, f'ES_{cname.upper()}_INDEX_MULTIPLEXED'):
            raise IndexNotMultiplexedException("""This command supports setting replicas
                                               only in secondary index of multiplexed Indices.""")
        if getattr(settings, f'ES_{cname.upper()}_INDEX_SWAPPED'):
            raise IndexAlreadySwappedException("Replicas can only be set before swapping indexes.")
        self._prepare_index_for_normal_usage(adapter.secondary)
        logger.info(f"Successfully set replicas for index {adapter.secondary.index_name}")


class Command(BaseCommand):
    """
    ES sync management command. It can be used to manage reindex processes on HQ indices.
    The command requires the index to be multiplexed before the reindex is started.
    This management command currently supports following subcommands

    For starting a reindex -
        ```bash
        ./manage.py elastic_sync_multiplexed start <index_cname>
        ```

        You can also specify batch size for the reindex command -

        ```bash
        ./manage.py elastic_sync_multiplexed start <index_cname> --batch_size <batch size>
        ```

        If reindex fails with `MapperParsingException[Field [_id] is a metadata field
        and cannot be added inside a document.Use the index API request parameters.]`

        The error can be fixed by

        ```
        ./manage.py elastic_sync_multiplexed start <index_cname> --purge-ids
        ```

    For removing tombstones from a index -
        ```bash
        ./manage.py elastic_sync_multiplexed cleanup <index_cname>
        ```

    For deleting an older CommcareHQ index after reindex is done.
        ```bash
        ./manage.py elastic_sync_multiplexed delete <index_cname>
        ```

    <index_cname> is the hq cannoical name for an index like forms, cases

    For cancelling an ongoing reindex -
        ```bash
        ./manage.py elastic_sync_multiplexed cancel <task_id>
        ```

    For getting status of existing reindex
        ```bash
        ./manage.py elastic_sync_multiplexed status <task_id>
        ```

    <task_id> is the reindex operation id that would be printed by start command.
    It would look like 'XDke_N9TQQCGqL-aEQNR7Q:1808229'

    For getting estimated disk space required for reindex operations -
        ```bash
        ./manage.py elastic_sync_multiplexed estimated_size_for_reindex
        ```

    For copying checkpoints from source index checkpoint ids to destination index checkpoint ids-
        ```bash
        ./manage.py elastic_sync_multiplexed copy_checkpoints <index_cname>
        ```

    If replicas are not set during the time of reindex, they can be set on secondary index by
        ```bash
        ./manage.py elastic_sync_multiplexed set_replicas <index_cname>
        ```
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
        start_cmd.add_argument(
            '--batch_size',
            type=int,
            default=1000,  # This is default batch size used by ES for reindex
            help="Reindex batch size"
        )

        start_cmd.add_argument(
            "--purge-ids",
            action="store_true",
            default=False,
            help="Add reindex script to remove ids from doc source. This slows down the reindex substantially,"
                 "but is necessary if existings docs contain _ids in the source, as it is now a reserved property."
        )

        start_cmd.add_argument(
            "--requests_per_second",
            default=None,
            type=int,
            help="""throttles rate at which reindex issues batches of
                    index operations by padding each batch with a wait time"""
        )

        start_cmd.add_argument(
            "--with-no-replicas",
            action="store_true",
            default=False,
            help="Replica shards will not be created for the destination index during reindex."
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

        clean_up_cmd = subparsers.add_parser("cleanup")
        clean_up_cmd.set_defaults(func=self.es_helper.perform_cleanup)
        clean_up_cmd.add_argument(
            'index_cname',
            choices=INDEXES,
            help="""Cannonical Name of the index where tombstones will be cleared""",
        )

        delete_index_cmd = subparsers.add_parser("delete")
        delete_index_cmd.set_defaults(func=self.es_helper.delete_index)
        delete_index_cmd.add_argument(
            'index_cname',
            choices=INDEXES,
            help="""Cannonical Name of the index whose older index should be deleted""",
        )

        estimate_size_cmd = subparsers.add_parser("estimated_size_for_reindex")
        estimate_size_cmd.set_defaults(func=self.es_helper.estimate_disk_space_for_reindex)

        # Copy checkpoints
        copy_checkpoint_cmd = subparsers.add_parser("copy_checkpoints")
        copy_checkpoint_cmd.set_defaults(func=self.es_helper.set_checkpoints_for_new_index)
        copy_checkpoint_cmd.add_argument(
            'index_cname',
            choices=INDEXES,
            help="""Cannonical Name of the index whose checkpoints are to be copied""",
        )

        # Set replicas for secondary index
        set_replicas_cmd = subparsers.add_parser("set_replicas")
        set_replicas_cmd.set_defaults(func=self.es_helper.set_replicas_for_secondary_index)
        set_replicas_cmd.add_argument(
            'index_cname',
            choices=INDEXES,
            help="""Cannonical Name of the index whose replicas are to be set"""
        )

    def handle(self, **options):
        sub_cmd = options['sub_command']
        cmd_func = options.get('func')
        if sub_cmd == 'start':
            cmd_func(
                options['index_cname'], options['batch_size'],
                options['purge_ids'], options['requests_per_second'],
                options['with_no_replicas']
            )
        elif sub_cmd == 'delete':
            cmd_func(options['index_cname'])
        elif sub_cmd == 'cleanup':
            cmd_func(doc_adapter_from_cname(options['index_cname']))
        elif sub_cmd == 'cancel' or sub_cmd == 'status':
            cmd_func(options['task_id'])
        elif sub_cmd == 'estimated_size_for_reindex':
            cmd_func(stdout=self.stdout)
        elif sub_cmd == 'copy_checkpoints':
            cmd_func(options['index_cname'])
        elif sub_cmd == 'set_replicas':
            cmd_func(options["index_cname"])
