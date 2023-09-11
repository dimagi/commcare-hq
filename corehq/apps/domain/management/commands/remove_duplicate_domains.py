from django.core.management import BaseCommand

from corehq.apps.domain.models import Domain


class Command(BaseCommand):
    help = "Detects and removes duplicate domains"

    def handle(self, **options):
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

            self.stdout.write('Found Dup: %s\n' % domain)
            self.stdout.write(" -- _id of correct domain: %s\n" % currently_chosen_domain_doc.get_id)
            self.stdout.write(" -- ids of duplicate domains: %s\n" % [d.get_id for d in other_domain_docs])

            for dom in other_domain_docs:
                dom.doc_type = 'Domain-DUPLICATE'
                dom.save()
