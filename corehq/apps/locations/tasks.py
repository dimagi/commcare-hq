from corehq.util.decorators import serial_task
from corehq.apps.commtrack.models import StockState, sync_supply_point
from corehq.apps.locations.models import SQLLocation


@serial_task("{location_type.domain}-{location_type.pk}",
             default_retry_delay=30, max_retries=3)
def sync_administrative_status(location_type, sync_supply_points=True):
    """Updates supply points of locations of this type"""
    if sync_supply_points:
        for location in SQLLocation.objects.filter(location_type=location_type):
            # Saving the location should be sufficient for it to pick up the
            # new supply point.  We'll need to save it anyways to store the new
            # supply_point_id.
            location.save()
    if location_type.administrative:
        _hide_stock_states(location_type)
    else:
        _unhide_stock_states(location_type)


def _hide_stock_states(location_type):
    (StockState.objects
     .filter(sql_location__location_type=location_type)
     .update(sql_location=None))


def _unhide_stock_states(location_type):
    for location in SQLLocation.objects.filter(location_type=location_type):
        (StockState.objects
         .filter(case_id=location.supply_point_id)
         .update(sql_location=location))


@serial_task("{domain}", default_retry_delay=30, max_retries=3)
def sync_supply_points(location_type):
    for location in SQLLocation.objects.filter(location_type=location_type):
        sync_supply_point(location)
        location.save()
