from datetime import datetime
from custom.ilsgateway.reminders import randr
from custom.ilsgateway.utils import supply_points_with_latest_status_by_datespan, get_current_group
from dimagi.utils.dates import DateSpan, get_business_day_of_month_before
from custom.ilsgateway.models import SupplyPointStatusTypes, SupplyPointStatusValues


def _construct_status_dict(status_type, status_values, supply_points, datespan):
    ret = {}
    for status in status_values:
        ret[status] = len(supply_points_with_latest_status_by_datespan\
                        (sps=supply_points,
                         status_type=status_type,
                         status_value=status,
                         datespan=datespan))
    ret["total"] = len(supply_points)
    ret["not_responding"] = len(supply_points) - \
                                sum(v for k, v in ret.items() if k != "total")
    return ret

def construct_summary(supply_point, status_type, values, cutoff):
    children = supply_point.location.children
    children = filter(lambda sp: get_current_group() in sp.metadata.get('groups', []), children)

    return _construct_status_dict(status_type,
                                 values,
                                  children, DateSpan(cutoff, datetime.utcnow()))
