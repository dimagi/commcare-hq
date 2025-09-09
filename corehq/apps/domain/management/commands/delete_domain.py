import textwrap

from django.core.management.base import BaseCommand

from corehq.apps.domain.dbaccessors import iter_all_domains_and_deleted_domains_with_name


class Command(BaseCommand):
    help = "Deletes the given domain and its contents"

    def add_arguments(self, parser):
        parser.add_argument(
            'domain_name',
        )

    def handle(self, domain_name, **options):
        domain_objs = list(iter_all_domains_and_deleted_domains_with_name(domain_name))
        if not domain_objs:
            print('domain with name "{}" not found'.format(domain_name))
            return
        if len(domain_objs) > 1:
            print("FYI: There are multiple domain objects for this domain"
                  "and they will all be soft-deleted.")
        confirm = input(textwrap.dedent(
            f"""
            Are you sure you want to delete the domain "{domain_name}" and all of it's data?
            This operation is not reversible and all forms and cases will be PERMANENTLY deleted.

            Type the domain's name again to continue, or anything else to cancel:
            """
        ))
        if confirm != domain_name:
            print("\n\t\tDomain deletion cancelled.")
            return
        print(f"Soft-Deleting domain {domain_name} "
              "(i.e. switching its type to Domain-Deleted, "
              "which will prevent anyone from reusing that domain)")
        for domain_obj in domain_objs:
            assert domain_obj.name == domain_name  # Just to be really sure!
            domain_obj.delete(leave_tombstone=True)
        print("Operation completed")
