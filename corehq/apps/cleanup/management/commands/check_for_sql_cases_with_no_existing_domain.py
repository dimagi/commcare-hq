from django.core.management import BaseCommand

from corehq.apps.domain.models import Domain
from corehq.form_processor.models import CommCareCaseSQL
from corehq.sql_db.util import get_db_aliases_for_partitioned_query

class Command(BaseCommand):

    def handle(self, **options):
        all_existing_domain_names = set(Domain.get_all_names())

        domain_names_in_sql_cases = set()
        for db_name in get_db_aliases_for_partitioned_query():
            domain_names_in_partition = CommCareCaseSQL.objects.using(db_name).values_list(
                'domain', flat=True).distinct()
            domain_names_in_sql_cases.update(set(domain_names_in_partition))

        print domain_names_in_sql_cases - all_existing_domain_names
