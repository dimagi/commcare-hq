from django.core.management.base import BaseCommand

from dimagi.utils.couch.database import iter_docs

from corehq.apps.domain.models import Domain


class Command(BaseCommand):

    def _get_domains_without_last_modified_date(self):
        docs = iter_docs(Domain.get_db(), [
            domain['id']
            for domain in Domain.view(
                "domain/domains",
                reduce=False,
                include_docs=False
            )
        ])
        return [x for x in docs if 'last_modified' not in x or not x['last_modified']]

    def handle(self, **options):
        for domain_doc in self._get_domains_without_last_modified_date():
            print("Updating domain {}".format(domain_doc['name']))
            domain = Domain.wrap(domain_doc)
            domain.save()
