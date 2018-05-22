from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import division
from corehq.apps.locations.models import SQLLocation
from corehq.util.quickcache import quickcache
from custom.icds_reports import const
import sqlalchemy
from sqlalchemy.sql import select, func, case
from corehq.sql_db.connections import connection_manager, ICDS_UCR_ENGINE_ID
from corehq.apps.userreports.util import get_table_name
from datetime import datetime

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
