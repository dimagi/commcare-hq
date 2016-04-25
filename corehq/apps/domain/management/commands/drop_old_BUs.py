from django.core.management.base import BaseCommand
from corehq.apps.domain.models import Domain
from corehq.util.couch import iter_update, DocUpdate
from corehq.util.log import with_progress_bar

VALID_BUSINESS_UNITS = {
    "DSA",
    "DSI",
    "DWA",
    "INC",
    "",
}


def migrate_domain(domain):
    business_unit = domain['internal'].get('business_unit', "")
    if business_unit in VALID_BUSINESS_UNITS:
        return
    elif business_unit == "DLAC":
        new_bu = "INC"
    elif business_unit == "DMOZ":
        new_bu = "DSA"
    else:
        new_bu = ""

    domain['internal']['business_unit'] = new_bu
    return DocUpdate(domain)


class Command(BaseCommand):
    help = "Migrates DLAC to INC and DMOZ to DSA"

    def handle(self, *args, **options):
        domain_ids = with_progress_bar(Domain.get_all_ids())
        res = iter_update(Domain.get_db(), migrate_domain, domain_ids, verbose=True)
        print "Updated domains:"
        print "\n".join(res.updated_ids)
