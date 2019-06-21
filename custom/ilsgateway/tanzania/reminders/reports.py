from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime

from corehq.apps.locations.dbaccessors import get_users_assigned_to_locations
from corehq.apps.locations.models import SQLLocation
from custom.ilsgateway.models import SupplyPointStatusTypes, SupplyPointStatusValues, \
    SupplyPointStatus
from custom.ilsgateway.utils import supply_points_with_latest_status_by_datespan
from dimagi.utils.dates import get_business_day_of_month_before


def get_district_people(domain):
    districts_ids = SQLLocation.objects.filter(
        location_type__name='DISTRICT',
        domain=domain
    ).values_list('location_id', flat=True)
    for sms_user in get_users_assigned_to_locations(domain):
        if sms_user.location_id in districts_ids:
            yield sms_user


def _construct_status_dict(status_type, status_values, locations, datespan):
    ret = {}
    for status in status_values:
        ret[status] = len(supply_points_with_latest_status_by_datespan(
            locations=locations,
            status_type=status_type,
            status_value=status,
            datespan=datespan
        ))
    ret["total"] = len(locations)
    ret["not_responding"] = len(locations) - sum(v for k, v in ret.items() if k != "total")
    return ret


def construct_summary(location, status_type, values, cutoff):
    locations = list(location.get_children())
    statuses = SupplyPointStatus.objects.filter(
        status_date__gte=cutoff,
        status_date__lte=datetime.utcnow(),
        status_type=status_type,
        status_value__in=values,
        location_id__in=[loc.get_id for loc in locations]
    ).distinct('location_id').order_by('location_id', '-status_date')
    ret = {}
    for value in values:
        ret[value] = 0

    for status in statuses:
        ret[status.status_value] += 1
    ret["total"] = len(locations)
    ret["not_responding"] = len(locations) - len(statuses)
    return ret


def construct_soh_summary(location):
    now = datetime.utcnow()
    return construct_summary(
        location,
        SupplyPointStatusTypes.SOH_FACILITY,
        [SupplyPointStatusValues.SUBMITTED],
        get_business_day_of_month_before(now.year, now.month, 5)
    )


def construct_delivery_summary(location):
    now = datetime.utcnow()
    return construct_summary(
        location,
        SupplyPointStatusTypes.DELIVERY_FACILITY,
        [SupplyPointStatusValues.RECEIVED, SupplyPointStatusValues.NOT_RECEIVED],
        get_business_day_of_month_before(now.year, now.month, 5)
    )
