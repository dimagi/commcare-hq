# Once-off migration created 2016-02-04
import sys

from collections import namedtuple
from dimagi.utils.decorators.memoized import memoized
from django.core.management.base import BaseCommand

from corehq.apps.domain.dbaccessors import get_doc_ids_in_domain_by_type
from corehq.apps.locations.dbaccessors import get_users_assigned_to_locations
from corehq.apps.locations.models import Location, SQLLocation, LocationType


LocSpec = namedtuple("LocSpec", "location_id site_code name parent_site_code")


clinic_ids = [
    "61cbd7878023c60e8164bf034eea15c1",
    "47a442c3f6da934617a38b58ec278861",
    "813ed20d5a98e28a563d9134444242be",
    "813ed20d5a98e28a563d9134444238cb",
    "813ed20d5a98e28a563d913444422ea9",
    "813ed20d5a98e28a563d91344442238d",
    "813ed20d5a98e28a563d913444422010",
    "813ed20d5a98e28a563d913444421bc6",
    "813ed20d5a98e28a563d913444421110",
    "813ed20d5a98e28a563d9134444208c4",
    "813ed20d5a98e28a563d91344441f9fd",
    "813ed20d5a98e28a563d91344441efdb",
    "813ed20d5a98e28a563d91344441e267",
    "813ed20d5a98e28a563d91344441d4b6",
    "813ed20d5a98e28a563d91344441c755",
]


chw_ids = [
    "47a442c3f6da934617a38b58ec8a4038",
    "73f227b6cae17c5e19074ade45088f51",
    "32d03ecd1ec961fcda01793765b386c4",
    "e01c742644c833346bfe95c6ac4ad0c1",
    "1a2c0a68285fc5a0905cbfbbee2a64a0",
    "813ed20d5a98e28a563d91344441b8d8",
    "813ed20d5a98e28a563d91344441aa6f",
    "813ed20d5a98e28a563d913444419d39",
    "813ed20d5a98e28a563d9134444199b9",
    "c72635bcebf0107266e19cbed00b3002",
    "c72635bcebf0107266e19cbed00b2d20",
    "2859c25c30a72982e1da3f482c5a0ebb",
    "813ed20d5a98e28a563d913444417c0b",
    "813ed20d5a98e28a563d91344441718f",
    "813ed20d5a98e28a563d913444415eb4",
    "813ed20d5a98e28a563d9134444154f8",
    "813ed20d5a98e28a563d913444419196",
    "7fb038f553df57f6c39f16b837dbcc58",
    "c72635bcebf0107266e19cbed00b1bc6",
    "c72635bcebf0107266e19cbed00b18bc",
    "813ed20d5a98e28a563d91344440ec85",
    "813ed20d5a98e28a563d91344440e04e",
    "813ed20d5a98e28a563d91344440caf8",
    "813ed20d5a98e28a563d91344440c14f",
    "813ed20d5a98e28a563d9134444106aa",
    "813ed20d5a98e28a563d91344440f82e",
    "813ed20d5a98e28a563d913444411ef7",
    "813ed20d5a98e28a563d913444411d58",
    "813ed20d5a98e28a563d913444410a68",
    "813ed20d5a98e28a563d9134444108ce",
    "813ed20d5a98e28a563d913444413a86",
    "813ed20d5a98e28a563d913444412f68",
]


domain = "spf-defaulters"

real_ids = clinic_ids + chw_ids


def confirm(msg):
    if raw_input(msg + "\n(y/n) ") != 'y':
        sys.exit()


class Command(BaseCommand):
    help = ''

    def __init__(self, *args, **kwargs):
        self.completed_locations = {}
        super(Command, self).__init__(*args, **kwargs)

    def get_couch_ids(self):
        return get_doc_ids_in_domain_by_type(domain, "Location")

    def get_sql_ids(self):
        return SQLLocation.objects.filter(domain=domain).location_ids()

    @property
    @memoized
    def clinic(self):
        return LocationType.objects.get(domain=domain, code="clinic")

    @property
    @memoized
    def chw(self):
        return LocationType.objects.get(domain=domain, code="clinic-chws")

    def show_info(self):
        print "There are {} real location ids\n".format(len(real_ids))

        couch_ids = self.get_couch_ids()
        print "There are {} Location docs in couch".format(len(couch_ids))
        print "{} of the real ids are in couch\n".format(len([
            loc for loc in real_ids if loc in couch_ids
        ]))

        sql_ids = self.get_sql_ids()
        print "There are {} SQLLocations".format(len(sql_ids))
        print "{} of the real ids are in SQL\n".format(len([
            loc for loc in real_ids if loc in sql_ids
        ]))

        print "The location types are clinic={} and chw={}\n".format(
            self.clinic, self.chw
        )

    def delete_bad_couch_locs(self):
        bad_ids = [loc for loc in self.get_couch_ids() if loc not in real_ids]
        confirm("Delete {} unrecognized Couch ids?".format(len(bad_ids)))
        for bad_id in bad_ids:
            Location.get(bad_id).delete()

    def delete_bad_sql_locs(self):
        bad_ids = [loc for loc in self.get_sql_ids() if loc not in real_ids]
        confirm("Delete {} unrecognized SQL ids?".format(len(bad_ids)))
        SQLLocation.objects.filter(location_id__in=bad_ids).delete()

    def resave_good_couch_locs(self, location_ids, location_type):
        print "Saving {} {} locations".format(len(location_ids), location_type.name)
        for loc_id in location_ids:
            couch_loc = Location.get(loc_id)
            couch_loc.location_type = location_type
            couch_loc.save()
            self.completed_locations[couch_loc.site_code] = couch_loc

    def get_mobile_worker_assignments(self):
        return [
            (user, user.location.site_code)
            for user in get_users_assigned_to_locations(domain)
        ]

    def reassign_mobile_workers(self, mobile_workers):
        for worker, site_code in mobile_workers:
            if site_code in self.completed_locations:
                worker.set_location(self.completed_locations[site_code])
            else:
                print "Couldn't find location {} for user {} {}".format(
                    site_code, worker.username, worker._id)

    def handle(self, *args, **options):
        mobile_workers = self.get_mobile_worker_assignments()
        print "Mobile worker assignments:"
        for worker, site_code in mobile_workers:
            print worker.username, site_code
        print ""

        self.show_info()
        confirm("Look okay?")

        self.delete_bad_couch_locs()
        self.delete_bad_sql_locs()

        self.show_info()
        confirm("Look okay?")

        self.resave_good_couch_locs(clinic_ids, self.clinic)
        self.resave_good_couch_locs(chw_ids, self.chw)

        self.show_info()
        print "I hope that worked, reassigning users."
        self.reassign_mobile_workers(mobile_workers)
        print "Done!"
