import sys

from django.core.management import BaseCommand

from corehq.apps.cleanup.tasks import _get_missing_domains
from corehq.apps.es import AppES, CaseES, CaseSearchES, FormES, GroupES, UserES
from corehq.apps.es.registry import registry_entry
from corehq.apps.es.transient_util import doc_adapter_from_info


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        deleted_domains = _get_missing_domains()
        if domain not in deleted_domains:
            print(f"{domain} has not been deleted. This command is intended for use on deleted domains only.")
            sys.exit(1)

        for hqESQuery in [AppES, CaseES, CaseSearchES, FormES, GroupES, UserES]:
            docs = hqESQuery().domain(domain).run().hits
            if not docs:
                continue
            adapter = doc_adapter_from_info(registry_entry(hqESQuery.index))
            adapter.bulk_delete(docs)
