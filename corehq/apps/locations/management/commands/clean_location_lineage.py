from optparse import make_option

from django.core.management.base import BaseCommand

from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import SQLLocation, Location


class Command(BaseCommand):
    help = "Cleans the location lineage properties for a domain. See http://manage.dimagi.com/default.asp?245138"
    args = '<domain>'

    option_list = (
        make_option('--noinput',
            action='store_true',
            dest='noinput',
            default=False,
            help='Skip important confirmation warnings.'),
    )

    def handle(self, *args, **options):
        domain_name = args[0].strip()
        domain = Domain.get_by_name(domain_name)
        if not domain:
            print u'domain with name "{}" not found'.format(domain_name)
            return

        sql_location_qs = SQLLocation.objects.filter(domain=domain_name)
        print 'checking {} locations for issues'.format(sql_location_qs.count())
        couch_locations_to_save = []
        for sql_location in sql_location_qs:
            if sql_location.lineage != sql_location.couch_location.lineage:
                print 'would change lineage of {} from {} to {}'.format(
                    sql_location.name,
                    '-->'.join(sql_location.couch_location.lineage),
                    '-->'.join(sql_location.lineage),
                )
                sql_location.couch_location.lineage = sql_location.lineage
                couch_locations_to_save.append(sql_location.couch_location.to_json())

        if couch_locations_to_save:
            if not options['noinput']:
                confirm = raw_input(
                    u"""
                    Would you like to commit these changes? {} locations will be affected. (y/n)
                    """.format(len(couch_locations_to_save))
                )
                if confirm != 'y':
                    print "\n\t\taborted"
                    return
            print u"Committing changes"
            Location.get_db().bulk_save(couch_locations_to_save)
            print "Operation completed"
        else:
            print 'no issues found'
