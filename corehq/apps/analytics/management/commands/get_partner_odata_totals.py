import os
from django.core.management import BaseCommand

from corehq.apps.export.dbaccessors import get_brief_exports


class Command(BaseCommand):
    help = "get total OData feeds for given partner"

    def handle(self, **options):
        with open(os.path.join(os.path.dirname(__file__), 'odata-domains.txt')) as f:
            domains = set([d.replace('\n', '').strip() for d in f.readlines()])

        total_feeds = 0
        self.stdout.write('\n\ntotals by domain')
        for domain in domains:
            total_for_domain = self._get_total_odata_feeds(domain)
            self.stdout.write(f'{domain}\t{total_for_domain}')
            total_feeds += total_for_domain

        self.stdout.write('-------------\n')
        self.stdout.write(f'TOTAL\t{total_feeds}')

    def _get_total_odata_feeds(self, domain):
        exports = get_brief_exports(domain)
        odata_feeds = [e for e in exports if e['is_odata_config']]
        return len(odata_feeds)
