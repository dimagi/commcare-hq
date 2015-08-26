from corehq.apps.facilities.models import FacilityRegistry


def get_facility_registries_in_domain(domain):
    return FacilityRegistry.view(
        'domain/docs',
        reduce=False,
        startkey=[domain, 'FacilityRegistry'],
        endkey=[domain, 'FacilityRegistry', {}],
        include_docs=True,
    ).all()
