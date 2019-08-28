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
            real_dom = Domain.get_by_name(domain)
            total_doms = Domain.view("domain/domains",
                key=domain,
                reduce=False,
                include_docs=True,
            ).all()
            fake_doms = [d for d in total_doms if d.get_id != real_dom.get_id]

            self.stdout.write('Found Dup: %s\n' % domain)
            self.stdout.write(" -- _id of correct domain: %s\n" % real_dom.get_id)
            self.stdout.write(" -- ids of duplicate domains: %s\n" % [d.get_id for d in fake_doms])

            for dom in fake_doms:
                dom.doc_type = 'Domain-DUPLICATE'
                dom.save()
