# One-off migration from 2016-04-04
from optparse import make_option
from time import sleep
from django.core.management.base import BaseCommand
from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.es import DomainES
from corehq.util.log import with_progress_bar


def get_affected_location_types():
    commtrack_domains = (DomainES()
                         .commtrack_domains()
                         .values_list('name', flat=True))
    return (LocationType.objects
            .exclude(domain__in=commtrack_domains)
            .filter(administrative=False))


def show_info():
    location_types = get_affected_location_types()
    num_locations = SQLLocation.objects.filter(location_type__in=location_types).count()
    print ("There are {domains} domains, {loc_types} loc types, and "
           "{locations} locations affected").format(
        domains=location_types.distinct('domain').count(),
        loc_types=location_types.count(),
        locations=num_locations,
    )


def run_migration():
    for location_type in with_progress_bar(get_affected_location_types()):
        if not location_type.administrative:
            location_type.administrative = True
            location_type.save()
            sleep(1)


class Command(BaseCommand):
    help = ('There are a bunch of LocationTypes on non-commtrack domains which'
            'incorrectly are marked as administrative=False')
    option_list = BaseCommand.option_list + (
        make_option('--run', action='store_true', default=False),
    )

    def handle(self, *args, **options):
        if options.get('run', False):
            run_migration()
        else:
            show_info()
            print "pass `--run` to run the migration"
