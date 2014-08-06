from datetime import datetime
from custom.ilsgateway.models import SupplyPointStatus
from django.utils.translation import ugettext as _

REMINDER_STOCKONHAND = _("Please send in your stock on hand information in the format 'soh <product> <amount> <product> <amount>...'")
REMINDER_R_AND_R_FACILITY = _("Have you sent in your R&R form yet for this quarter? Please reply \"submitted\" or \"not submitted\"")
REMINDER_R_AND_R_DISTRICT = _("How many R&R forms have you submitted to MSD? Reply with 'submitted A <number of R&Rs submitted for group A> B <number of R&Rs submitted for group B>'")
REMINDER_DELIVERY_FACILITY = _("Did you receive your delivery yet? Please reply 'delivered <product> <amount> <product> <amount>...'")
REMINDER_DELIVERY_DISTRICT = _("Did you receive your delivery yet? Please reply 'delivered' or 'not delivered'")
REMINDER_SUPERVISION = _("Have you received supervision this month? Please reply 'supervision yes' or 'supervision no'")

SOH_HELP_MESSAGE = _("To report stock on hand, send SOH [space] [product code] [space] [amount]")
SUPERVISION_HELP = _("Supervision reminders will come monthly, and you can respond 'supervision yes' if you have received supervision or 'supervision no' if you have not")


DELIVERY_CONFIRM_DISTRICT = _("Thank you %(contact_name)s for reporting your delivery for %(facility_name)s")
DELIVERY_PARTIAL_CONFIRM = _("To record a delivery, respond with \"delivered product amount product amount...\"")

SUBMITTED_NOTIFICATION_MSD = _("%(district_name)s has submitted their R&R forms to MSD: %(group_a)s for Group A, %(group_b)s for Group B, %(group_c)s for Group C")
DELIVERY_CONFIRM_CHILDREN = _("District %(district_name)s has reported that they sent their R&R forms to MSD")


def update_statuses(supply_point_ids, type, value):
    for supply_point_id in supply_point_ids:
        now = datetime.utcnow()
        SupplyPointStatus.objects.create(supply_point=supply_point_id,
                                         status_type=type,
                                         status_value=value,
                                         status_date=now)
