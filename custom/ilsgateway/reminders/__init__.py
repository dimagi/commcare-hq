from datetime import datetime
from custom.ilsgateway.models import SupplyPointStatus

REMINDER_STOCKONHAND = "Please send in your stock on hand information in the format 'soh <product> <amount> <product> <amount>...'"


def update_status(supply_point_id, type, value):
    now = datetime.utcnow()
    SupplyPointStatus.objects.create(supply_point=supply_point_id,
                                         status_type=type,
                                         status_value=value,
                                         status_date=now)