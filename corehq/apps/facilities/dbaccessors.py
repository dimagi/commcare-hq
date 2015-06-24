from corehq.apps.facilities.models import FacilityRegistry


def get_facility_registries_in_domain(domain):
    return FacilityRegistry.view(
        'facilities/registries_by_domain',
        reduce=False,
        key=domain,
        include_docs=True,
    ).all()
