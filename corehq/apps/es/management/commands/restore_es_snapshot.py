from django.core.management.base import BaseCommand, CommandError
from datetime import datetime, timedelta
from corehq.elastic import get_es_new
from elasticsearch.client import SnapshotClient, IndicesClient
from django.conf import settings

class Command(BaseCommand):
    help = "Restores ES cluster from snapshot"
    args = "days_ago"

    def handle(self, *args, **options):
        print "Restoring ES indices from snapshot"
        if len(args) != 1:
            raise CommandError('Usage is restore_es_snapshot %s' % self.args)
        date = self.process_arguments(args)
        es = get_es_new()
        self.close_indices(es)
        self.restore_snapshot(es, date)
    
    @staticmethod
    def process_arguments(args):
        days_ago = args[0]
        restore_date = (datetime.utcnow() - timedelta(days=days_ago))
        return restore_date

    @staticmethod
    def close_indices(es):
        indices_client = IndicesClient(es)
        indices_client.close('_all')

    @staticmethod
    def restore_snapshot(es, date):
        snapshot_client = SnapshotClient(es)
        env = settings.SERVER_ENVIRONMENT
        repo_name = '{}_es_snapshot'.format(env)
        snapshot_client.restore(repo_name, '{repo_name}_{year}_{month}_{day}'.format(
            repo_name=repo_name, year=date.year, month=date.month, day=date.day)
        )
