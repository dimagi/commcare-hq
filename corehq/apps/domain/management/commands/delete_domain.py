from django.core.management.base import BaseCommand

from corehq.apps.domain.dbaccessors import iter_all_domains_and_deleted_domains_with_name
from corehq.apps.domain.models import Domain


class Command(BaseCommand):
    help = "Deletes the given domain and its contents"

    def add_arguments(self, parser):
        parser.add_argument(
            'domain_name',
        )
        parser.add_argument(
            '--noinput',
            action='store_true',
            dest='noinput',
            default=False,
            help='Skip important confirmation warnings.',
        )

    def handle(self, domain_name, **options):
        domain_objs = list(iter_all_domains_and_deleted_domains_with_name(domain_name))
        if not domain_objs:
            print('domain with name "{}" not found'.format(domain_name))
            return
        if len(domain_objs) > 1:
            print("FYI: There are multiple domain objects for this domain"
                  "and they will all be soft-deleted.")
        if not options['noinput']:
            confirm = input(
                """
                Are you sure you want to delete the domain "{}" and all of it's data?
                This operation is not reversible and all forms and cases will be PERMANENTLY deleted.

                Type the domain's name again to continue, or anything else to cancel:
                """.format(domain_name)
            )
            if confirm != domain_name:
                print("\n\t\tDomain deletion cancelled.")
                return
        print("Soft-Deleting domain {} "
              "(i.e. switching its type to Domain-Deleted, "
              "which will prevent anyone from reusing that domain)"
              .format(domain_name))
        for domain_obj in domain_objs:
            domain_obj.delete(leave_tombstone=True)
        print("Operation completed")
