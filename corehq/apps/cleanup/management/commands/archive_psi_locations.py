from django.core.management.base import BaseCommand
import time
from corehq.apps.locations.models import Location
from corehq.apps.commtrack.util import generate_code
from dimagi.utils.couch.database import iter_docs

PSI_DOMAINS = (
    "drewpsi",
    "psi",
    "psi-ors",
    "psi-test",
    "psi-test2",
    "psi-test3",
    "psi-unicef",
    "psi-unicef-wb",
)

class Command(BaseCommand):
    help = 'Archive all psi locations, by changing their doc type'

    def handle(self, *args, **options):
        relevant_ids = set([r['id'] for r in Location.get_db().view(
            'locations/by_type',
            reduce=False,
        ).all()])

        total_locs = len(relevant_ids)
        print 'processing {} locations'.format(total_locs)
        total_saved = 0
        queue = []
        for i, loc in enumerate(iter_docs(Location.get_db(), relevant_ids)):
            if loc['domain'] in PSI_DOMAINS:
                loc['doc_type'] = 'Location-Deleted'
                queue.append(loc)

            if len(queue) > 500:
                Location.get_db().bulk_save(queue)
                total_saved += len(queue)
                queue = []
                print 'saved {} locations ({}/{} seen)'.format(total_saved, i, total_locs)
                time.sleep(5)

        if queue:
            total_saved += len(queue)
            Location.get_db().bulk_save(queue)

        print 'successfully archived {}/{} locations'.format(total_saved, total_locs)
