import sys

from django.core.management import BaseCommand

from corehq.apps.domain.models import Domain
from corehq.apps.es import AppES, CaseES, CaseSearchES, FormES, GroupES, UserES
from corehq.apps.es.registry import registry_entry
from corehq.apps.es.transient_util import doc_adapter_from_info


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        domain_obj = Domain.get_by_name(domain)
        if domain_obj and not domain_obj.doc_type.endswith('-Deleted'):
            print(f"{domain} has not been deleted. This command is intended for use on deleted domains only.")
            sys.exit(1)

        for hqESQuery in [AppES, CaseES, CaseSearchES, FormES, GroupES, UserES]:
            doc_ids = hqESQuery().domain(domain).source(['_id']).run().hits
            if not doc_ids:
                continue
            adapter = doc_adapter_from_info(registry_entry(hqESQuery.index))
            adapter.bulk_delete(doc_ids)
