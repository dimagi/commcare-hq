from datetime import datetime
from custom.ilsgateway.models import SupplyPointStatus
from django.utils.translation import ugettext_lazy as _

CONTACT_SUPERVISOR = _('Sorry, I could not understand your message. Please contact your supervisor for help.')

REGISTER_HELP = _(
    "To register send reg <name> <msd code> or reg <name> at <district name>. "
    "Example:reg john patel d34002 or reg john patel : tandahimba"
)
REGISTER_BAD_CODE = _(
    "I didn't recognize your msd code.  "
    "To register, send register <name> <msd code>. example: register Peter Juma d34002"
)
REGISTER_UNKNOWN_CODE = _("Sorry, can't find the location with MSD CODE %(msd_code)s")
REGISTER_UNKNOWN_DISTRICT = _("Sorry, can't find the location with the name %(name)s")
REGISTRATION_CONFIRM = _("Thank you for registering at %(sdp_name)s, %(msd_code)s, %(contact_name)s")
REGISTRATION_CONFIRM_DISTRICT = _("Thank you for registering at %(sdp_name)s, %(contact_name)s")

REMINDER_STOCKONHAND = _(
    "Please send in your stock on hand information"
    "in the format 'soh <product> <amount> <product> <amount>...'"
)
REMINDER_R_AND_R_FACILITY = _(
    "Have you sent in your R&R form yet for this quarter? "
    "Please reply \"submitted\" or \"not submitted\""
)
REMINDER_R_AND_R_DISTRICT = _(
    "How many R&R forms have you submitted to MSD? "
    "Reply with 'submitted A <number of R&Rs submitted for group A>"
    " B <number of R&Rs submitted for group B>'"
)
REMINDER_DELIVERY_FACILITY = _(
    "Did you receive your delivery yet? "
    "Please reply 'delivered <product> <amount> <product> <amount>...'"
)
REMINDER_DELIVERY_DISTRICT = _("Did you receive your delivery yet? Please reply 'delivered' or 'not delivered'")
REMINDER_SUPERVISION = _(
    "Have you received supervision this month? "
    "Please reply 'supervision yes' or 'supervision no'"
)

SOH_HELP_MESSAGE = _("Please send in your stock on hand information in the format"
                     " 'soh <product> <amount> <product> <amount>...'")
SOH_THANK_YOU = _("Thank you for reporting your stock on hand this month")
SOH_CONFIRM = _(
    "Thank you. Please send in your adjustments in the format 'la <product> +-<amount> +-<product> +-<amount>...'"
)
SOH_PARTIAL_CONFIRM = _(
    'Thank you %(contact_name)s for reporting your stock on hand for %(facility_name)s.'
    '  Still missing %(product_list)s.'
)
SOH_BAD_FORMAT = _("Sorry, invalid format. "
                   "The message should be in the format 'soh <product> <amount> <product> <amount>...'")


SUPERVISION_HELP = _(
    "Supervision reminders will come monthly, and you can respond 'supervision yes' "
    "if you have received supervision or 'supervision no' if you have not"
)
SUPERVISION_CONFIRM_NO = _('You have reported that you have not yet received supervision this month.')
SUPERVISION_CONFIRM_YES = _('Thank you for reporting that you have received supervision this month.')
SUPERVISION_REMINDER = _(
    "Have you received supervision this month? "
    "Please reply 'supervision yes' or 'supervision no'"
)
SUBMITTED_REMINDER_FACILITY = _(
    "Have you sent in your R&R form yet for this quarter? "
    "Please reply \"submitted\" or \"not submitted\""
)
SUBMITTED_REMINDER_DISTRICT = _(
    "How many R&R forms have you submitted to MSD? "
    "Reply with 'submitted A <number of R&Rs submitted for group A> "
    "B <number of R&Rs submitted for group B>'"
)

NOT_DELIVERED_CONFIRM = _("You have reported that you haven't yet received your delivery.")

DELIVERED_CONFIRM = _("Thank you, you reported a delivery of %(reply_list)s. If incorrect, please resend.")
DELIVERY_CONFIRM_DISTRICT = _("Thank you %(contact_name)s for reporting your delivery for %(facility_name)s")
DELIVERY_PARTIAL_CONFIRM = _("To record a delivery, respond with \"delivered product amount product amount...\"")
DELIVERY_REMINDER_FACILITY = _(
    "Did you receive your delivery yet? "
    "Please reply 'delivered <product> <amount> <product> <amount>...'"
)
DELIVERY_REMINDER_DISTRICT = _("Did you receive your delivery yet? Please reply 'delivered' or 'not delivered'")
DELIVERY_LATE_DISTRICT = _(
    "Facility deliveries for group %(group_name)s (out of %(group_total)d): "
    "%(not_responded_count)d haven't responded and %(not_received_count)d have reported "
    "not receiving. See ilsgateway.com"
)

NOT_SUBMITTED_CONFIRM = _("You have reported that you haven't yet sent in your R&R.")

SUBMITTED_NOTIFICATION_MSD = _(
    "%(district_name)s has submitted their R&R forms to MSD: %(group_a)s for "
    "Group A, %(group_b)s for Group B, %(group_c)s for Group C"
)
SUBMITTED_CONFIRM = _("Thank you %(contact_name)s for submitting your R and R form for %(sp_name)s")
DELIVERY_CONFIRM_CHILDREN = _("District %(district_name)s has reported that they sent their R&R forms to MSD")

ARRIVED_HELP = _("To report an arrival, please send 'arrived <MSD code>'.")
ARRIVED_DEFAULT = _("Thank you for confirming your arrival at the health facility.")
ARRIVED_KNOWN = _("Thank you for confirming your arrival at %(facility)s.")

HELP_REGISTERED = _(
    'Welcome to ILSGateway. Available commands are soh, delivered, not delivered, submitted, '
    'not submitted, language, sw, en, stop, supervision, la'
)
HELP_UNREGISTERED = REGISTER_HELP


# language keyword
LANGUAGE_HELP = _("To set your language, send LANGUAGE <CODE>")
LANGUAGE_CONTACT_REQUIRED = _("You must JOIN or IDENTIFY yourself before you can set your language preference")
LANGUAGE_CONFIRM = _("I will speak to you in %(language)s.")
LANGUAGE_UNKNOWN = _('Sorry, I don\'t speak "%(language)s".')

STOP_CONFIRM = _(
    "You have requested to stop reminders to this number. "
    "Send 'help' to this number for instructions on how to reactivate."
)

YES_HELP = _(
    'If you have submitted your R&R, respond \"submitted\". '
    'If you have received your delivery, respond \"delivered\"'
)

#test handler
TEST_HANDLER_HELP = _(
    "To test a reminder, send \"test [remindername] [msd code]\"; "
    "valid tests are soh, delivery, randr. Remember to setup your contact details!"
)
TEST_HANDLER_BAD_CODE = _("Invalid msd code %(code)s")
TEST_HANDLER_CONFIRM = _("Sent")

LOSS_ADJUST_HELP = _("Please send in your adjustments in the format "
                     "'la <product> +-<amount> +-<product> +-<amount>...'")
LOSS_ADJUST_BAD_FORMAT = _("Sorry, invalid format.  The message should be in the format"
                           " 'la <product> +-<amount> +-<product> +-<amount>...")
LOSS_ADJUST_CONFIRM = _("Thank you. Have you received supervision this month? "
                        "Please reply 'supervision yes' or 'supervision no'")

STOCKOUT_CONFIRM = _('Thank you %(contact_name)s '
                     'for reporting stockouts of %(product_names)s for %(facility_name)s.')


# reminder reports
REMINDER_MONTHLY_RANDR_SUMMARY = _(
    "R&R - %(submitted)s/%(total)s submitted, %(not_submitted)s/%(total)s "
    "did not submit, %(not_responding)s/%(total)s did not reply"
)
REMINDER_MONTHLY_SOH_SUMMARY = _(
    "SOH - %(submitted)s/%(total)s reported, %(not_responding)s/%(total)s "
    "did not reply"
)
REMINDER_MONTHLY_DELIVERY_SUMMARY = _(
    "Deliveries - %(received)s/%(total)s received, %(not_received)s/%(total)s "
    "did not receive, %(not_responding)s/%(total)s did not reply"
)


HSA = "hsa"


class Roles(object):
    """
    Roles go here
    """
    HSA = HSA
    SENIOR_HSA = "sh"
    IN_CHARGE = "ic"
    CLUSTER_SUPERVISOR = "cs"
    DISTRICT_SUPERVISOR = "ds"
    DISTRICT_PHARMACIST = "dp"
    IMCI_COORDINATOR = "im"
    ALL_ROLES = {
        HSA: "hsa",
        SENIOR_HSA: "senior hsa",
        IN_CHARGE: "in charge",
        CLUSTER_SUPERVISOR: "cluster supervisor",
        DISTRICT_SUPERVISOR: "district supervisor",
        DISTRICT_PHARMACIST: "district pharmacist",
        IMCI_COORDINATOR: "imci coordinator"
    }

class Languages(object):
    """
    These are used in ILSGateway
    """
    ENGLISH = "en"
    SWAHILI = "sw"
    DEFAULT = SWAHILI


def update_statuses(supply_point_ids, type, value):
    for supply_point_id in supply_point_ids:
        now = datetime.utcnow()
        SupplyPointStatus.objects.create(location_id=supply_point_id,
                                         status_type=type,
                                         status_value=value,
                                         status_date=now)
