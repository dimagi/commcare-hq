from __future__ import print_function
from optparse import make_option

from django.core.management.base import BaseCommand

from corehq.apps.domain.models import Domain


class Command(BaseCommand):
    help = "Deletes the given domain and its contents"
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
            print(u'domain with name "{}" not found'.format(domain_name))
            return
        if not options['noinput']:
            confirm = raw_input(
                u"""
                Are you sure you want to delete the domain "{}" and all of it's data?
                This operation is not reversible and all forms and cases will be PERMANENTLY deleted.

                Type the domain's name again to continue, or anything else to cancel:
                """.format(domain_name)
            )
            if confirm != domain_name:
                print("\n\t\tDomain deletion cancelled.")
                return
        print(u"Deleting domain {}".format(domain_name))
        domain.delete()
        print("Operation completed")
