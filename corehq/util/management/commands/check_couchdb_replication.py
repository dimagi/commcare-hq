from __future__ import absolute_import, print_function

import json

from django.core.management import CommandError
from django.core.management.base import BaseCommand

from corehq.util.couchdb_management import couch_config


class Command(BaseCommand):
    help = "Check status or cancel replication"

    def add_arguments(self, parser):
        parser.add_argument('replication_id')
        parser.add_argument('--cancel', action='store_true')

    def handle(self, replication_id, cancel, **options):
        server = couch_config.get_db(None).server
        tasks = server.active_tasks()
        replication_tasks = {
            task['replication_id']: task for task in tasks
            if task['type'] == 'replication'
        }

        task = replication_tasks.get(replication_id)
        if not task:
            raise CommandError('Not replication task found with ID: {}'.format(replication_id))

        if cancel:
            response = server.res.post('/_replicate', payload={
                'replication_id': replication_id,
                'cancel': True
            })
            if response['ok']:
                print('Replication cancelled')
            else:
                print(json.dumps(response, indent=4))
        else:
            print(json.dumps(task, indent=4))
