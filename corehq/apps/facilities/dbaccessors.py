from corehq.apps.facilities.models import FacilityRegistry


def get_facility_registries_in_domain(domain):
    return FacilityRegistry.view(
        'by_domain_doc_type/view',
        reduce=False,
        key=[domain, 'FacilityRegistry'],
        include_docs=True,
    ).all()
