from corehq import Domain
from corehq.apps.commtrack.models import SupplyPointCase


def get_supply_point_by_external_id(domain, external_id):
    return SupplyPointCase.view('hqcase/by_domain_external_id',
        key=[domain, str(external_id)],
        reduce=False,
        include_docs=True,
        limit=1
    ).first()
