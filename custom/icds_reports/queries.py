from __future__ import absolute_import
from corehq.apps.locations.models import SQLLocation
from corehq.util.quickcache import quickcache
from custom.icds_reports import const


@quickcache(['domain'], timeout=5 * 60)
def get_test_state_locations_id(domain):
    return [
        sql_location.location_id
        for sql_location in SQLLocation.by_domain(domain).filter(location_type__code=const.LocationTypes.STATE)
        if sql_location.metadata.get('is_test_location', 'real') == 'test'
    ]
