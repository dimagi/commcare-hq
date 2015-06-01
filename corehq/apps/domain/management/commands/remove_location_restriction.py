from django.core.management import BaseCommand
from corehq.util.couch import iter_update, DocUpdate
from corehq.apps.domain.models import Domain


class Command(BaseCommand):
    help = "Change the location_restriction flag to False"

    def handle(self, *args, **options):
        def update_domain(doc):
            doc['location_restriction_for_users'] = False
            return DocUpdate(doc)
        domain_ids = [d['id'] for d in Domain.get_all(include_docs=False)]
        res = iter_update(Domain.get_db(), update_domain, domain_ids)

        print "number of domains updated:", len(res.updated_ids)
        print "Domains that already had it disabled:", res.ignored_ids
        print "Not Found:", res.not_found_ids
        print "Deleted (sure as shit better be empty):", res.deleted_ids
        print "Errored:", res.error_ids
