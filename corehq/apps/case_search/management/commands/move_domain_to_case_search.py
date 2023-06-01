from datetime import datetime

from django.core.management import BaseCommand

from corehq.apps.es import CaseES, CaseSearchES
from corehq.pillows.case_search import CaseSearchReindexerFactory, domain_needs_search_index


class Command(BaseCommand):
    """Moves domain case data to Case Search Index

    """

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        self.print_summary([domain])
        self.stdout.write('\n\n')
        confirm = input(f'\nActually migrate "{domain}"? [y/n] ')
        if not confirm == 'y':
            self.stdout.write('\nAborting migration\n\n')
            return

        self.migrate_domain(domain)

    def migrate_domain(self, domain):
        time_started = datetime.utcnow()
        self.stdout.write(f"Migrating {domain}...\n")
        domain_needs_search_index.clear(domain)
        CaseSearchReindexerFactory(domain=domain).build().reindex()
        task_time = datetime.utcnow() - time_started
        self.stdout.write(f'\nDone...\ntook {task_time.seconds} seconds\n\n\n\n')

    def print_summary(self, domains):
        max_space = '\t' * (int(max([len(x) for x in domains]) / 8) + 2)
        header = 'Domain{}CaseES\t\tCaseSearchES\n'.format(max_space)
        divider = '{}\n'.format('*' * (len(header) + len(max_space) * 8))
        self.stdout.write(divider)
        self.stdout.write(header)
        self.stdout.write(divider)
        for domain in domains:
            spacer = max_space[int(len(domain) / 8):]
            total_case_es = CaseES().domain(domain).count()
            total_case_search = CaseSearchES().domain(domain).count()
            self.stdout.write(f"{domain}{spacer}{total_case_es}\t\t{total_case_search}\n")
