from corehq.apps.locations.models import SQLLocation
from custom.icds_reports import const


def get_test_state_locations_id(domain):
    return [
        sql_location.location_id
        for sql_location in SQLLocation.by_domain(domain).filter(location_type__code=const.LocationTypes.STATE)
        if sql_location.metadata.get('is_test_location', 'real') == 'test'
    ]
