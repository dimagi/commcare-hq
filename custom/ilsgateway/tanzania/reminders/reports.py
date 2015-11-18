from datetime import datetime

from custom.ilsgateway.utils import supply_points_with_latest_status_by_datespan, get_current_group
from dimagi.utils.dates import DateSpan


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
    return _construct_status_dict(status_type, values, location.children, DateSpan(cutoff, datetime.utcnow()))
