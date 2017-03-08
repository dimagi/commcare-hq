from __future__ import print_function
from django.core.management.base import BaseCommand, CommandError
from datetime import date, timedelta
from corehq.elastic import get_es_new
from elasticsearch.client import SnapshotClient, IndicesClient
from django.conf import settings
from pillowtop.utils import get_all_pillow_instances
from corehq.apps.hqadmin.models import ESRestorePillowCheckpoints
from pillowtop.checkpoints.manager import DEFAULT_EMPTY_CHECKPOINT_SEQUENCE


class Command(BaseCommand):
    help = ("Restores full ES cluster or specific index from snapshot. "
            "Index arguments are optional and it will default to a full "
            "cluster restore if none are specified")
    args = "days_ago <index_1> <index_2> ..."

    def handle(self, *args, **options):
        print("Restoring ES indices from snapshot")
        if len(args) < 1:
            raise CommandError('Usage is restore_es_snapshot %s' % self.args)
        date = self.get_date(args)
        indices = self.get_indices(args)
        confirm = raw_input("This command will close the following es indices to reads and writes "
                            "for its duration: {}. Are you sure "
                            "you wish to continue? (y/n)".format(indices))
        if confirm.lower() != "y":
            return
        pillows = raw_input("Have you stopped all pillows? (y/n)")
        if pillows.lower() != "y":
            return
        es = get_es_new()
        client = self.get_client_and_close_indices(es, indices)
        try:
            self.restore_snapshot(es, date, indices)
        except:
            client.open(indices)
        self.rewind_pillows(date)

    @staticmethod
    def get_date(args):
        days_ago = int(args[0])
        restore_date = (date.today() - timedelta(days=days_ago))
        return restore_date

    @staticmethod
    def get_indices(args):
        if len(args) > 1:
            indices = ','.join(args[1:])
        else:
            indices = '_all'
        return indices

    @staticmethod
    def get_client_and_close_indices(es, indices):
        indices_client = IndicesClient(es)
        indices_client.close(indices)
        return indices_client

    @staticmethod
    def restore_snapshot(es, date, indices):
        snapshot_client = SnapshotClient(es)
        env = settings.SERVER_ENVIRONMENT
        repo_name = '{}_es_snapshot'.format(env)
        kwargs = {}
        if indices != '_all':
            kwargs['body'] = {'indices': indices}
        snapshot_client.restore(repo_name,
                                '{repo_name}_{year}_{month}_{day}'.format(
                                    repo_name=repo_name, year=date.year,
                                    month=date.month, day=date.day
                                ),
                                wait_for_completion=True,
                                **kwargs)

    @staticmethod
    def rewind_pillows(date):
        for pillow in get_all_pillow_instances():
            checkpoint = pillow.checkpoint
            try:
                checkpoint = ESRestorePillowCheckpoints.objects.get(checkpoint_id=checkpoint.checkpoint_id,
                                                                    date_updated=date)
                seq = checkpoint.seq
            except ESRestorePillowCheckpoints.DoesNotExist:
                seq = DEFAULT_EMPTY_CHECKPOINT_SEQUENCE

            pillow.checkpoint.update_to(seq)
