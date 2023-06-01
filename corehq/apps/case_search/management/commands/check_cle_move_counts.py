from datetime import datetime

from django.core.management import BaseCommand

from corehq.apps.case_search.models import DomainsNotInCaseSearchIndex
from corehq.apps.domain.models import Domain
from corehq.apps.es import CaseES, CaseSearchES
from dimagi.utils.couch.database import iter_docs


class Command(BaseCommand):
    """Runs data integrity checks to verify domains
    """

    def handle(self, **options):
        all_domain_ids = [d['id'] for d in Domain.get_all(include_docs=False)]
        date_of_move = datetime(2023, 4, 1)
        for domain_doc in iter_docs(Domain.get_db(), all_domain_ids):
            domain_obj = Domain.wrap(domain_doc)
            if domain_obj.date_created > date_of_move:
                continue
            total_case_es = CaseES().domain(domain_obj.name).count()
            total_case_search = CaseSearchES().domain(domain_obj.name).count()
            difference = total_case_es - total_case_search

            if (difference >= 100
                    and not DomainsNotInCaseSearchIndex.objects.filter(domain=domain_obj.name)):
                self.stdout.write(f"{domain_obj.name}\t{difference}\t{total_case_es}\t{total_case_search}")
                DomainsNotInCaseSearchIndex.objects.create(domain=domain_obj.name, estimated_size=difference)
