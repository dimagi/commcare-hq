from __future__ import print_function

from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand
from datetime import date, timedelta
from corehq.elastic import get_es_new
from elasticsearch.client import SnapshotClient, IndicesClient
from django.conf import settings
from pillowtop.models import str_to_kafka_seq
from pillowtop.utils import get_all_pillow_instances
from corehq.apps.hqadmin.models import HistoricalPillowCheckpoint
from six.moves import input


DEFAULT_EMPTY_CHECKPOINT_SEQUENCE_FOR_RESTORE = {
    'text': '0',
    'json': {}
}


class Command(BaseCommand):
    help = ("Restores full ES cluster or specific index from snapshot. "
            "Index arguments are optional and it will default to a full "
            "cluster restore if none are specified")

    def add_arguments(self, parser):
        parser.add_argument(
            'days_ago',
        )
        parser.add_argument(
            'indices',
            metavar='index',
            nargs='*',
        )

    def handle(self, days_ago, indices, **options):
        print("Restoring ES indices from snapshot")
        date = self.get_date(days_ago)
        indices = self.get_indices(indices)
        confirm = input("This command will close the following es indices to reads and writes "
                            "for its duration: {}. Are you sure "
                            "you wish to continue? (y/n)".format(indices))
        if confirm.lower() != "y":
            return
        pillows = input("Have you stopped all pillows? (y/n)")
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
    def get_date(days_ago):
        days_ago = int(days_ago)
        restore_date = (date.today() - timedelta(days=days_ago))
        return restore_date

    @staticmethod
    def get_indices(indices):
        if indices:
            return ','.join(indices)
        else:
            return '_all'

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
                checkpoint = HistoricalPillowCheckpoint.objects.get(checkpoint_id=checkpoint.checkpoint_id,
                                                                    date_updated=date)
                if pillow.checkpoint.sequence_format == 'json':
                    seq = str_to_kafka_seq(checkpoint.seq)
                else:
                    seq = checkpoint.seq
            except HistoricalPillowCheckpoint.DoesNotExist:
                seq = DEFAULT_EMPTY_CHECKPOINT_SEQUENCE_FOR_RESTORE[pillow.checkpoint.sequence_format]

            pillow.checkpoint.update_to(seq)
