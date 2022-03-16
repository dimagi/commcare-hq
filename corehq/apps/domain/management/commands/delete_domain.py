import textwrap

from django.core.management.base import BaseCommand
from django.db.models import Q

from dimagi.utils.chunked import chunked

from corehq.apps.domain.dbaccessors import iter_all_domains_and_deleted_domains_with_name
from corehq.apps.domain.utils import silence_during_tests
from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.sql_db.util import (
    estimate_partitioned_row_count,
    paginate_query_across_partitioned_databases,
)
from corehq.util.log import with_progress_bar


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
        self.hard_delete_cases(domain_name)
        self.hard_delete_forms(domain_name)
        print(f"Soft-Deleting domain {domain_name} "
              "(i.e. switching its type to Domain-Deleted, "
              "which will prevent anyone from reusing that domain)")
        for domain_obj in domain_objs:
            assert domain_obj.name == domain_name  # Just to be really sure!
            domain_obj.delete(leave_tombstone=True)
        print("Operation completed")

    @staticmethod
    def hard_delete_cases(domain_name):
        print("Hard-deleting cases...")
        case_ids = iter_ids(CommCareCase, 'case_id', domain_name)
        for chunk in chunked(case_ids, 1000, list):
            CommCareCase.objects.hard_delete_cases(domain_name, chunk)

    @staticmethod
    def hard_delete_forms(domain_name):
        print("Hard-deleting forms...")
        form_ids = iter_ids(XFormInstance, 'form_id', domain_name)
        for chunk in chunked(form_ids, 1000, list):
            XFormInstance.objects.hard_delete_forms(domain_name, chunk)


def iter_ids(model_class, field, domain, chunk_size=1000):
    where = Q(domain=domain)
    rows = paginate_query_across_partitioned_databases(
        model_class,
        where,
        values=[field],
        load_source='delete_domain',
        query_size=chunk_size,
    )
    yield from with_progress_bar(
        (r[0] for r in rows),
        estimate_partitioned_row_count(model_class, where),
        prefix="",
        oneline="concise",
        stream=silence_during_tests(),
    )
