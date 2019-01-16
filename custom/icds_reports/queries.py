from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import division
from corehq.apps.locations.models import SQLLocation
from corehq.util.quickcache import quickcache
from custom.icds_reports import const

from custom.icds_reports.models.helper import IcdsFile

DATA_NOT_ENTERED = "Data Not Entered"


@quickcache(['domain'], timeout=5 * 60)
def get_test_state_locations_id(domain):
    return [
        sql_location.location_id
        for sql_location in SQLLocation.by_domain(domain).filter(location_type__code=const.LocationTypes.STATE)
        if sql_location.metadata.get('is_test_location', 'real') == 'test'
    ]


@quickcache(['domain'], timeout=5 * 60)
def get_test_district_locations_id(domain):
    return [
        sql_location.location_id
        for sql_location in SQLLocation.by_domain(domain).filter(location_type__code=const.LocationTypes.DISTRICT)
        if sql_location.metadata.get('is_test_location', 'real') == 'test'
    ]


def get_cas_data_blob_file(indicator, location, date):
    indicators = ['', 'child_health_monthly', 'ccs_record_monthly', 'agg_awc']
    blob_id = "{}-{}-{}".format(
        indicators[indicator],
        location,
        date
    )
    try:
        return IcdsFile.objects.get(blob_id=blob_id), blob_id
    except IcdsFile.DoesNotExist:
        return None, None
