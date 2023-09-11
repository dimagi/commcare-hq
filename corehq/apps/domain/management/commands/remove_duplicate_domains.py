from django.core.management import BaseCommand

from corehq.apps.domain.models import Domain


class Command(BaseCommand):
    help = "Detects and removes duplicate domains"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', default=False)

    def handle(self, dry_run, **options):
        domains = Domain.get_all()
        seen = set([])
        dups = set([])
        for domain in domains:
            if domain.name in seen:
                dups.add(domain.name)
            else:
                seen.add(domain.name)

        if not dups:
            self.stdout.write('Found no duplicate domains\n')

        for domain in list(dups):
            currently_chosen_domain_doc = Domain.get_by_name(domain)
            all_domain_docs = Domain.view("domain/domains",
                key=domain,
                reduce=False,
                include_docs=True,
            ).all()
            other_domain_docs = [d for d in all_domain_docs if d.get_id != currently_chosen_domain_doc.get_id]

            self.stdout.write(f'Found duplicate docs for domain: {domain}\n')
            self.stdout.write(f'Chosen\t{"_id":32}\t{"name":16}\tis_active\t{"date_created":26}\t{"_rev":32}\n')

            for domain_doc in all_domain_docs:
                chosen = domain_doc._id == currently_chosen_domain_doc._id
                chosen_str = '-->' if chosen else ''
                self.stdout.write(f'{chosen_str}\t{domain_doc._id}\t{domain_doc.name:16}\t{str(domain_doc.is_active):9}\t{domain_doc.date_created}\t{domain_doc._rev}\n')

            if not dry_run:
                for dom in other_domain_docs:
                    dom.doc_type = 'Domain-DUPLICATE'
                    dom.save()
