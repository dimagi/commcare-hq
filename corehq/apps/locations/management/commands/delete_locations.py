import time
from django.core.management.base import BaseCommand
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.couch.undo import DELETED_SUFFIX
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import Location, SQLLocation
from .check_loc_types import locs_by_domain


class Command(BaseCommand):
    args = "<domain>"
    help = ("Change the doc types of all locations in `domain` to "
            "Location-Deleted.  Note that this only affects couch locations.")

    def bulk_delete_locs(self, loc_ids, total):
        locs_to_save = []
        count = 0
        for loc in iter_docs(Location.get_db(), loc_ids):
            loc['doc_type'] = "{}{}".format(loc['doc_type'], DELETED_SUFFIX)
            loc['is_archived'] = True
            locs_to_save.append(loc)
            count += 1

            if len(locs_to_save) > 100:
                Location.get_db().bulk_save(locs_to_save)
                locs_to_save = []
                print "{} of {}".format(count, total)
                time.sleep(5)

        if locs_to_save:
            Location.get_db().bulk_save(locs_to_save)

    def handle(self, *args, **options):
        if not len(args) == 1:
            print "Format is ./manage.py delete_locations {}".format(self.args)
            return

        domain = args[0]
        domain_obj = Domain.get_by_name(domain)
        if domain_obj is None:
            print "Domain '{}' not found".format(domain)
            return

        couch_total = locs_by_domain(domain)
        sql_total = SQLLocation.objects.filter(domain=domain).count()
        msg = ("{} has {} Locations and {} SQLLocations, do you REALLY want "
               "to delete them?\n(y/n)"
               .format(domain, couch_total, sql_total))
        if raw_input(msg) != 'y':
            return

        print "Fine, your funeral"
        print '"Deleting" couch locs'
        self.bulk_delete_locs(
            Location.by_domain(domain, include_docs=False),
            couch_total,
        )

        print "Archiving SQLLocations"
        SQLLocation.objects.filter(domain=domain).update(is_archived=True)
        print "Finished"
