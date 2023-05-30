from django.core.management import BaseCommand, CommandError

from corehq.apps.domain.models import Domain
from corehq.apps.es import AppES, CaseES, CaseSearchES, FormES, GroupES, UserES
from corehq.apps.es.transient_util import doc_adapter_from_cname


class Command(BaseCommand):
    """
    Intended for use in the event that a domain has been deleted, but ES docs have not been fully cleaned up
    """

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        domain_obj = Domain.get_by_name(domain)
        if domain_obj and not domain_obj.doc_type.endswith('-Deleted'):
            raise CommandError(
                f"{domain} has not been deleted. This command is intended for use on deleted domains only."
            )

        for hqESQuery in [AppES, CaseES, CaseSearchES, FormES, GroupES, UserES]:
            doc_ids = hqESQuery().domain(domain).source(['_id']).run().hits
            doc_ids = [doc['_id'] for doc in doc_ids]
            if not doc_ids:
                continue
            adapter = doc_adapter_from_cname(hqESQuery.index)
            adapter.bulk_delete(doc_ids)
            print(f"Deleted {len(doc_ids)} documents in the {hqESQuery.index} index for {domain}")
