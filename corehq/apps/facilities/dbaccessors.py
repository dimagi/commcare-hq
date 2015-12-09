from corehq.apps.facilities.models import FacilityRegistry


def get_facility_registries_in_domain(domain):
    return FacilityRegistry.view(
        'by_domain_doc_type_date/view',
        reduce=False,
        startkey=[domain, 'FacilityRegistry'],
        endkey=[domain, 'FacilityRegistry', {}],
        include_docs=True,
    ).all()
