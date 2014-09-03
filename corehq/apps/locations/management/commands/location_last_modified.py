from django.core.management.base import BaseCommand
from corehq.apps.locations.models import Location
from dimagi.utils.couch.database import iter_docs
from datetime import datetime

class Command(BaseCommand):
    help = 'Populate last_modified field for locations'

    def handle(self, *args, **options):
        self.stdout.write("Processing locations...\n")

        relevant_ids = set([r['id'] for r in Location.get_db().view(
            'commtrack/locations_by_code',
            reduce=False,
        ).all()])

        to_save = []

        for location in iter_docs(Location.get_db(), relevant_ids):
            # exclude any psi domain to make this take a realistic
            # amount fo time
            if (
                not location.get('last_modified', False) and
                'psi' not in location.get('domain', '')
            ):
                location['last_modified'] = datetime.now().isoformat()
                to_save.append(location)

                if len(to_save) > 500:
                    Location.get_db().bulk_save(to_save)
                    to_save = []

        if to_save:
            Location.get_db().bulk_save(to_save)
