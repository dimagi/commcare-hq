from __future__ import absolute_import
from __future__ import unicode_literals

from django.core.management import BaseCommand
from django.db.models import Q

from corehq.apps.accounting.models import (
    Subscription,
    SoftwarePlanEdition,
)
from corehq.apps.domain.models import Domain
from corehq.apps.es import CaseES, CaseSearchES
from corehq.pillows.case_search import (
    domains_needing_search_index,
    CaseSearchReindexerFactory,
)
from corehq.toggles import ECD_MIGRATED_DOMAINS, NAMESPACE_DOMAIN


class Command(BaseCommand):
    help = 'Enables the Case Search Index for Explore Case Data Report'

    def add_arguments(self, parser):
        parser.add_argument(
            '--bulk-num',
            action='store',
            dest='bulk_num',
            type=int,
            default=5,
            help='The number of domains to migrate in bulk (default functionality).'
        )
        parser.add_argument(
            '--domain',
            action='store',
            dest='domain',
            default=None,
            help='A single domain to migrate.'
        )
        parser.add_argument(
            '--status',
            action='store_true',
            dest='status',
            default=False,
            help='Show status of remaining domains.'
        )

    @staticmethod
    def _domains_in_explore_case_data_beta():
        relevant_subs = Subscription.visible_objects.filter(
            is_active=True,
            is_trial=False,
        ).filter(
            Q(plan_version__plan__edition=SoftwarePlanEdition.ADVANCED) |
            Q(plan_version__plan__edition=SoftwarePlanEdition.PRO) |
            Q(plan_version__plan__edition=SoftwarePlanEdition.ENTERPRISE)
        ).all()
        return [sub.subscriber.domain for sub in relevant_subs]

    @staticmethod
    def _migrated_domains():
        return domains_needing_search_index()

    def _get_domain_lists(self):
        migrated = self._migrated_domains()
        couch_domains = []
        remaining = []

        for domain in self._domains_in_explore_case_data_beta():
            if domain in migrated:
                pass
            elif not Domain.get_by_name(domain).use_sql_backend:
                couch_domains.append(domain)
            else:
                remaining.append(domain)
        return remaining, couch_domains, migrated

    def handle(self, **options):
        bulk_num = options.pop('bulk_num')
        domain = options.pop('domain')
        status = options.pop('status')

        self.stdout.write('\n\n')

        remaining, couch_domains, migrated = self._get_domain_lists()

        if status:
            self.show_status(remaining, couch_domains, migrated)
            return

        if domain:
            self.print_totals([domain])
            self.stdout.write('\n\n')
            confirm = raw_input('\nActually migrate "{}"? [y/n] '.format(domain))
            if not confirm == 'y':
                self.stdout.write('\nAborting migration\n\n')
                return

            self.migrate_domain(domain)
        elif not remaining:
            self.stdout.write('No sql domains needing migration\n\n\n')
            if couch_domains:
                self.stdout.write('Migrate these couch domains individually:\n')
                self.stdout.write('\n'.join(couch_domains))
                self.stdout.write('\n\n')
            return
        else:
            self.bulk_migrate(remaining, bulk_num)

    def bulk_migrate(self, domains, num_to_migrate):
        num_domains = len(domains)
        num_to_migrate = min(num_domains, num_to_migrate)
        domains_to_migrate = domains[:num_to_migrate]

        self.stdout.write('Migrating {} of {} domains.\n\n'.format(
            num_to_migrate, num_domains
        ))
        self.print_totals(domains_to_migrate)
        self.stdout.write('\n\n')

        confirm = raw_input('\nContinue with migration? [y/n] ')
        if not confirm == 'y':
            self.stdout.write('\nAborting migration\n\n')
            return

        self.stdout.write('\n\n')
        for domain in domains_to_migrate:
            self.migrate_domain(domain)

    def migrate_domain(self, domain):
        self.stdout.write('Migrating {}...\n'.format(domain))
        ECD_MIGRATED_DOMAINS.set(domain, True, NAMESPACE_DOMAIN)
        domains_needing_search_index.clear()
        CaseSearchReindexerFactory(domain=domain).build().reindex()
        self.stdout.write('Done...\n\n'.format(domain))

    def show_status(self, remaining, couch_domains, migrated):
        if remaining:
            self.stdout.write('\n\nDomains Needing Migration:\n')
            self.stdout.write('\n'.join(remaining))
        if couch_domains:
            self.stdout.write('\n\nCouch Domains Needing Careful Migration:\n')
            self.stdout.write('\n'.join(couch_domains))
        if migrated:
            self.stdout.write('\n\nDomains Already Migrated:\n')
            self.print_totals(migrated)
        self.stdout.write('\n\n')

    def print_totals(self, domains):
        max_space = '\t' * (max(map(lambda x: len(x), domains))/8 + 2)
        header = 'Domain{}CaseES\t\tCaseSearchES\n'.format(max_space)
        divider = '{}\n'.format('*' * (len(header) + len(max_space) * 8))
        self.stdout.write(divider)
        self.stdout.write(header)
        self.stdout.write(divider)
        for domain in domains:
            spacer = max_space[len(domain)/8:]
            total_case_es = CaseES().domain(domain).count()
            total_case_search = CaseSearchES().domain(domain).count()
            self.stdout.write('{domain}{spacer}{case_es}\t\t{case_search}\n'.format(
                domain=domain,
                spacer=spacer,
                case_es=total_case_es,
                case_search=total_case_search,
            ))
