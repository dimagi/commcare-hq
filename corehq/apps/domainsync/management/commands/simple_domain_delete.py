from optparse import make_option
from django.core.management.base import BaseCommand, CommandError
from corehq.apps.domain.models import Domain

class Command(BaseCommand):
    help = "Deletes the contents of a domain"
    args = '<domain>'

    option_list = BaseCommand.option_list + (
        make_option('--simulate',
                    action='store_true',
                    dest='simulate',
                    default=False,
                    help='Don\'t delete anything, print what would be deleted.'),
    )

    def handle(self, *args, **options):
        print "Deleting domain"
        domain = args[0].strip()
        try:
            Domain.get_by_name(domain).delete()
        except Exception, e:
            print "Delete failed! Error is: %s" % e
            import traceback
            traceback.print_exc()
