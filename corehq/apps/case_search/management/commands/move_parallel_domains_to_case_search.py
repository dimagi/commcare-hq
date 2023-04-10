from datetime import datetime
from multiprocessing import cpu_count, Pool

from django.core.management import BaseCommand
from django.db.models import Sum

from corehq.apps.case_search.models import DomainsNotInCaseSearchIndex
from corehq.pillows.case_search import CaseSearchReindexerFactory, domain_needs_search_index


class Command(BaseCommand):
    """Moves domain case data to Case Search Index (multi threaded)
    """

    def add_arguments(self, parser):
        parser.add_argument('lowest_size')
        parser.add_argument('highest_size')
        parser.add_argument('max_domains')

    def handle(self, lowest_size, highest_size, max_domains, **options):
        domains = DomainsNotInCaseSearchIndex.objects.filter(
            estimated_size__gte=int(lowest_size)
        ).filter(
            estimated_size__lte=int(highest_size)
        ).all()[:int(max_domains)]

        num_domains = domains.count()
        num_cases = domains.aggregate(Sum('estimated_size'))['estimated_size__sum']

        confirm = input(f'\nMigrate {num_domains} domains with {num_cases} cases to Case Search Index [y/n] ')
        if confirm:
            self.stdout.write("Migrating...\n")
            time_started = datetime.utcnow()
            pool = Pool(processes=cpu_count())
            pool.map(self.migrate_domain, domains)
            task_time = datetime.utcnow() - time_started
            self.stdout.write(f'\nDone...\ntook {task_time.seconds} seconds\n\n\n\n')

    def migrate_domain(self, domain):
        domain_needs_search_index.clear(domain)
        DomainsNotInCaseSearchIndex.objects.filter(domain=domain).delete()
        CaseSearchReindexerFactory(domain=domain).build().reindex()
