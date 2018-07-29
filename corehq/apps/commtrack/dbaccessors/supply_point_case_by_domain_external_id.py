from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.commtrack.models import SupplyPointCase


def get_supply_point_case_by_domain_external_id(domain, external_id):
    return SupplyPointCase.view('cases_by_domain_external_id/view',
                                key=[domain, str(external_id)],
                                reduce=False,
                                include_docs=True,
                                limit=1).first()
