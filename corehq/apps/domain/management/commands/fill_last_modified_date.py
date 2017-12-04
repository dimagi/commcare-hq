from __future__ import print_function
from __future__ import absolute_import
from django.core.management.base import BaseCommand

from corehq.apps.domain.models import Domain
from dimagi.utils.couch.database import iter_docs


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
