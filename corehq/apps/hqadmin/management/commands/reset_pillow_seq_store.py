from __future__ import print_function
from optparse import make_option
from django.core.management.base import BaseCommand

from corehq.apps.hqadmin.models import PillowCheckpointSeqStore


class Command(BaseCommand):
    help = 'Reset a PillowCheckpointSeqStore back to 0'

    def add_arguments(self, parser):
        parser.add_argument('--pillow_name', action='store', default=None, help='Pillow name to reset store')

    def handle(self, **options):

        pillow_name = options.get('pillow_name', None)
        if not pillow_name:
            print('Please supply a pillow name')
            exit()

        store = PillowCheckpointSeqStore.get_by_pillow_name(pillow_name)
        if not store:
            print('Unable to find PillowCheckpointSeqStore for pillow: {}'.format(pillow_name))
            exit()
        store.seq = 0
        store.save()

        print('Successfully set {} back to 0'.format(pillow_name))
