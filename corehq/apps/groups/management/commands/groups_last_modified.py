from django.core.management.base import BaseCommand
from corehq.apps.groups.models import Group
from dimagi.utils.couch.database import iter_docs
from datetime import datetime

class Command(BaseCommand):
    help = 'Populate last_modified field for groups'

    def handle(self, *args, **options):
        self.stdout.write("Processing groups...\n")

        relevant_ids = set([r['id'] for r in Group.get_db().view(
            'groups/all_groups',
            reduce=False,
        ).all()])

        to_save = []

        for group in iter_docs(Group.get_db(), relevant_ids):
            if 'last_modified' not in group or not group['last_modified']:
                print group['_id']
                group['last_modified'] = datetime.utcnow().isoformat()
                to_save.append(group)

                if len(to_save) > 500:
                    Group.get_db().bulk_save(to_save)
                    to_save = []

        if to_save:
            Group.get_db().bulk_save(to_save)
