from django.core.management.base import BaseCommand
from dimagi.utils.couch.database import iter_docs
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import Location
from .check_loc_types import locs_by_domain


class Command(BaseCommand):
    args = "<domain>"
    help = ("Change the doc types of all locations in `domain` to "
            "Location-DELETED.  Note that this only affects couch locations.")

    def bulk_delete_locs(self, loc_ids):
        locs_to_save = []
        count = 0
        for loc in iter_docs(Location.get_db(), loc_ids):
            loc['doc_type'] = "{}-DELETED".format(loc['doc_type'])
            locs_to_save.append(loc)
            count += 1

            if len(locs_to_save) > 100:
                Location.get_db().bulk_save(locs_to_save)
                locs_to_save = []
                print "{} of {}".format(count, total)

        if locs_to_save:
            Location.get_db().bulk_save(locs_to_save)
        print "Finished"

    def handle(self, *args, **options):
        if not len(args) == 1:
            print "Format is ./manage.py delete_locations {}".format(self.args)
            return

        domain = Domain.get_by_name(args[0])
        if domain is None:
            print "Domain '{}' not found".format(args[0])
            return

        total = locs_by_domain(domain.name)
        msg = ("{} has {} locations, do you REALLY want to delete them?\n(y/n)"
               .format(domain.name, total))
        if raw_input(msg) != 'y':
            return

        print "Fine, your funeral"

        self.bulk_delete_locs(
            Location.by_domain(domain.name, include_docs=False)
        )
