from __future__ import print_function

from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand

from corehq.apps.locations.models import SQLLocation, LocationType
from six.moves import input


class Command(BaseCommand):
    help = "Make "

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry_run',
            action='store_true',
            dest='dry_run',
            default=False,
            help='Just check what domains have problems',
        )
        parser.add_argument(
            '--noinput',
            action='store_true',
            dest='noinput',
            default=False,
            help='Skip important confirmation warnings.',
        )

    def handle(self, **options):
        domains = (SQLLocation.objects
                   .order_by('domain')
                   .distinct('domain')
                   .values_list('domain', flat=True))
        for domain in domains:
            if has_bad_location_types(domain):
                print("{} has bad location types".format(domain))
                if not options['dry_run']:
                    if options['noinput'] or input("fix? (y/N)").lower() == 'y':
                        fix_domain(domain)


def fix_domain(domain):
    locs_w_bad_types = (SQLLocation.objects
                        .filter(domain=domain)
                        .exclude(location_type__domain=domain))
    print("found {} locs with bad types".format(locs_w_bad_types.count()))
    bad_types = LocationType.objects.filter(sqllocation__in=locs_w_bad_types).distinct()
    assert domain not in bad_types.values_list('domain', flat=True)

    bad_to_good = {}
    for bad_type in bad_types:
        good_type = LocationType.objects.get(domain=domain, code=bad_type.code)
        bad_to_good[bad_type.code] = good_type
    print("successfully found corresponding loctypes on the domain for each misreferenced loctype")

    for loc in locs_w_bad_types:
        loc.location_type = bad_to_good[loc.location_type.code]
        loc.save()


def has_bad_location_types(domain):
    return (SQLLocation.objects
            .filter(domain=domain)
            .exclude(location_type__domain=domain)
            .exists())
