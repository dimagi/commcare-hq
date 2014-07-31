from datetime import datetime
from custom.ilsgateway.models import SupplyPointStatus
from django.utils.translation import ugettext as _

REMINDER_STOCKONHAND = _("Please send in your stock on hand information in the format 'soh <product> <amount> <product> <amount>...'")
REMINDER_R_AND_R_FACILITY = _("Have you sent in your R&R form yet for this quarter? Please reply \"submitted\" or \"not submitted\"")


def update_status(supply_point_id, type, value):
    now = datetime.utcnow()
    SupplyPointStatus.objects.create(supply_point=supply_point_id,
                                         status_type=type,
                                         status_value=value,
                                         status_date=now)