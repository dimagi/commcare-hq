from corehq.apps.locations.models import SQLLocation
from corehq.apps.es.case_search import CaseSearchES


def get_user_facility_ids(domain, restore_user):
    # Facility locations the user is either directly assigned to, or which are
    # children of organizations the user is assigned to
    owned_locs = (restore_user.get_sql_locations(domain)
                  .filter(location_type__code__in=['organization', 'facility']))
    return list(SQLLocation.objects
                .get_queryset_descendants(owned_locs, include_self=True)
                .filter(location_type__code='facility')
                .location_ids())


def get_user_clinic_ids(domain, restore_user, facility_ids):
    return " ".join(
        CaseSearchES()
        .domain(domain)
        .case_type('clinic')
        .is_closed(False)
        .owner(facility_ids)
        .get_ids()
    )
