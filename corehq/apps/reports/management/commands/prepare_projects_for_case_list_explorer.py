from datetime import datetime

from django.core.management import BaseCommand

from dimagi.utils.couch.database import iter_docs
from corehq.apps.case_search.models import DomainsNotInCaseSearchIndex
from corehq.apps.domain.models import Domain
from corehq.apps.es import CaseES, CaseSearchES
from corehq.pillows.case_search import CaseSearchReindexerFactory, domain_needs_search_index


class Command(BaseCommand):
    """Helper tool for preparing legacy projects on CommCare HQ instances for the General Release
    of Case List Explorer. This is done by ensuring data is synced between the Elasticsearch CaseIndex
    and CaseSearchIndex.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--project',
            action='store',
            dest='domain',
            help='Specify a specific project to run a data integrity check '
                 '(verify case counts in both indices) and re-sync.'
        )

    def handle(self, **options):
        domain = options.pop('domain')
        if domain is not None:
            if DomainsNotInCaseSearchIndex.objects.count() > 0:
                self.stdout.write("Please finish running the complete initial sync by "
                                  "running this management command without the --project "
                                  "argument.")
                return
            self.run_domain_re_sync(domain)
            return

        self.migrate_domains_not_in_case_search_index()
        self.stdout.write("Initial sync complete.")
        self.run_data_integrity_checks()

    def migrate_domains_not_in_case_search_index(self):
        count = DomainsNotInCaseSearchIndex.objects.count()
        if count > 0:
            self.stdout.write(f"\n\nFound {count} project(s) to sync...")

            confirm = input("Please make sure you run this command inside a terminal multiplexer "
                            "like tmux or screen as this could take some time. Ready to continue? [y/n] ")
            if confirm.lower() != 'y':
                self.stdout.write("Aborting initial sync...")
                return
        else:
            return

        # delete DomainsNotInCaseSearchIndex for zero-case domains
        for zero_tracker in DomainsNotInCaseSearchIndex.objects.filter(estimated_size__lte=0).all():
            domain_needs_search_index.clear(zero_tracker.domain)
            zero_tracker.delete()

        for tracker in DomainsNotInCaseSearchIndex.objects.order_by('estimated_size').all():
            self.stdout.write(f"\n\nSyncing {tracker.domain}'s with {tracker.estimated_size} cases...")
            domain_needs_search_index.clear(tracker.domain)
            DomainsNotInCaseSearchIndex.objects.filter(domain=tracker.domain).delete()
            CaseSearchReindexerFactory(domain=tracker.domain).build().reindex()
            self.stdout.write(f"\nCompleted syncing {tracker.domain}...\n-----\n")

    def run_domain_re_sync(self, domain, total_case=None, total_case_search=None):
        if total_case is None:
            total_case = CaseES().domain(domain).count()
            total_case_search = CaseSearchES().domain(domain).count()
            self.stdout.write(f"\nProject {domain} has {total_case} cases in CaseIndex "
                              f"and {total_case_search} cases in CaseSearchIndex.")
            confirm = input("Would you like to re-sync this project? [y/n] ")
            if confirm.lower() != 'y':
                self.stdout.write("Aborting data integrity sync...")
                return

        self.stdout.write(f"\n\nRe-syncing {domain} with {total_case} cases...")
        CaseSearchReindexerFactory(domain=domain).build().reindex()
        self.stdout.write(f"\nCompleted syncing {domain}.\n"
                          f"Previous total synced was {total_case_search}...\n-----\n")

    def run_data_integrity_checks(self):
        if DomainsNotInCaseSearchIndex.objects.count() > 0:
            # don't run data integrity checks unless DomainsNotInCaseSearchIndex are all deleted
            return

        self.stdout.write("\n\nRunning data integrity checks...")
        domain_mismatches = []
        all_domain_ids = [d['id'] for d in Domain.get_all(include_docs=False)]
        date_of_move = datetime(2023, 4, 1)
        for domain_doc in iter_docs(Domain.get_db(), all_domain_ids):
            domain_obj = Domain.wrap(domain_doc)
            if domain_obj.date_created > date_of_move:
                continue
            total_case = CaseES().domain(domain_obj.name).count()
            total_case_search = CaseSearchES().domain(domain_obj.name).count()
            difference = total_case - total_case_search

            if difference >= 1:
                domain_mismatches.append((domain_obj.name, total_case, total_case_search))
        if len(domain_mismatches) > 0:
            self.stdout.write(f"Found {len(domain_mismatches)} project(s) with mismatched case numbers"
                              f"between Case Index and Case Search Index:")
            self.stdout.write("Project\tCaseIndex Total\tCaseSearchIndex Total\tDifference")
            for domain, total_case, total_case_search in domain_mismatches:
                self.stdout.write(f"{domain}\t{total_case}\t{total_case_search}\t{total_case - total_case_search}")
            confirm = input("Would you like to try and re-sync these projects? [y/n] ")
            if confirm.lower() != 'y':
                self.stdout.write("Aborting data integrity sync...")
                return

        for domain, total_case, total_case_search in domain_mismatches:
            self.run_domain_re_sync(domain, total_case, total_case_search)
