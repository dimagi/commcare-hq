from datetime import datetime
from custom.ilsgateway.models import SupplyPointStatus

REGISTER_HELP = ("To register send reg <name> <msd code> or reg <name> at <district name>. "
                 "Example:reg john patel d34002 or reg john patel : tandahimba")
REGISTER_BAD_CODE = ("I didn't recognize your msd code.  "
                     "To register, send register <name> <msd code>. example: register Peter Juma d34002")
REGISTER_UNKNOWN_CODE = "Sorry, can't find the location with MSD CODE %(msd_code)s"
REGISTER_UNKNOWN_DISTRICT = "Sorry, can't find the location with the name %(name)s"
REGISTRATION_CONFIRM = "Thank you for registering at %(sdp_name)s, %(msd_code)s, %(contact_name)s"
REGISTRATION_CONFIRM_DISTRICT = "Thank you for registering at %(sdp_name)s, %(contact_name)s"

REMINDER_STOCKONHAND = ("Please send in your stock on hand information"
                        "in the format 'soh <product> <amount> <product> <amount>...'")
REMINDER_R_AND_R_FACILITY = ("Have you sent in your R&R form yet for this quarter? "
                             "Please reply \"submitted\" or \"not submitted\"")
REMINDER_R_AND_R_DISTRICT = ("How many R&R forms have you submitted to MSD? "
                             "Reply with 'submitted A <number of R&Rs submitted for group A>"
                             " B <number of R&Rs submitted for group B>'")
REMINDER_DELIVERY_FACILITY = ("Did you receive your delivery yet? "
                              "Please reply 'delivered <product> <amount> <product> <amount>...'")
REMINDER_DELIVERY_DISTRICT = "Did you receive your delivery yet? Please reply 'delivered' or 'not delivered'"
REMINDER_SUPERVISION = ("Have you received supervision this month? "
                        "Please reply 'supervision yes' or 'supervision no'")

SOH_HELP_MESSAGE = "To report stock on hand, send SOH [space] [product code] [space] [amount]"
SOH_THANK_YOU = "Thank you for reporting your stock on hand this month"

SUPERVISION_HELP = ("Supervision reminders will come monthly, and you can respond 'supervision yes' "
                    "if you have received supervision or 'supervision no' if you have not")
SUPERVISION_CONFIRM_NO = 'You have reported that you have not yet received supervision this month.'
SUPERVISION_CONFIRM_YES = 'Thank you for reporting that you have received supervision this month.'
SUPERVISION_REMINDER = ("Have you received supervision this month? "
                        "Please reply 'supervision yes' or 'supervision no'")
SUBMITTED_REMINDER_FACILITY = ("Have you sent in your R&R form yet for this quarter? "
                               "Please reply \"submitted\" or \"not submitted\"")
SUBMITTED_REMINDER_DISTRICT = ("How many R&R forms have you submitted to MSD? "
                               "Reply with 'submitted A <number of R&Rs submitted for group A> "
                               "B <number of R&Rs submitted for group B>'")

NOT_DELIVERED_CONFIRM = "You have reported that you haven't yet received your delivery."

DELIVERY_CONFIRM_DISTRICT = "Thank you %(contact_name)s for reporting your delivery for %(facility_name)s"
DELIVERY_PARTIAL_CONFIRM = "To record a delivery, respond with \"delivered product amount product amount...\""
DELIVERY_REMINDER_FACILITY = ("Did you receive your delivery yet? "
                              "Please reply 'delivered <product> <amount> <product> <amount>...'")
DELIVERY_REMINDER_DISTRICT = "Did you receive your delivery yet? Please reply 'delivered' or 'not delivered'"
DELIVERY_LATE_DISTRICT = ("Facility deliveries for group %(group_name)s (out of %(group_total)d): "
                          "%(not_responded_count)d haven't responded and %(not_received_count)d have reported "
                          "not receiving. See ilsgateway.com")

NOT_SUBMITTED_CONFIRM = "You have reported that you haven't yet sent in your R&R."

SUBMITTED_NOTIFICATION_MSD = ("%(district_name)s has submitted their R&R forms to MSD: %(group_a)s for "
                              "Group A, %(group_b)s for Group B, %(group_c)s for Group C")
SUBMITTED_CONFIRM = "Thank you %(contact_name)s for submitting your R and R form for %(sp_name)s"
DELIVERY_CONFIRM_CHILDREN = "District %(district_name)s has reported that they sent their R&R forms to MSD"

ARRIVED_HELP = "To report an arrival, please send 'arrived <MSD code>'."
ARRIVED_DEFAULT = "Thank you for confirming your arrival at the health facility."
ARRIVED_KNOWN = "Thank you for confirming your arrival at %(facility)s."

HELP_REGISTERED = ('Welcome to ILSGateway. Available commands are soh, delivered, not delivered, submitted, '
                   'not submitted, language, sw, en, stop, supervision, la')
HELP_UNREGISTERED = REGISTER_HELP


# language keyword
LANGUAGE_HELP = ("To set your language, send LANGUAGE <CODE>")
LANGUAGE_CONTACT_REQUIRED = ("You must JOIN or IDENTIFY yourself before you can set your language preference")
LANGUAGE_CONFIRM = ("I will speak to you in %(language)s.")
LANGUAGE_UNKNOWN = ('Sorry, I don\'t speak "%(language)s".')

STOP_CONFIRM = ("You have requested to stop reminders to this number. "
                "Send 'help' to this number for instructions on how to reactivate.")

YES_HELP = ('If you have submitted your R&R, respond \"submitted\". '
            'If you have received your delivery, respond \"delivered\"')

#test handler
TEST_HANDLER_HELP = ("To test a reminder, send \"test [remindername] [msd code]\"; "
                     "valid tests are soh, delivery, randr. Remember to setup your contact details!")
TEST_HANDLER_BAD_CODE = ("Invalid msd code %(code)s")
TEST_HANDLER_CONFIRM = ("Sent")


# reminder reports
REMINDER_MONTHLY_RANDR_SUMMARY = ("R&R - %(submitted)s/%(total)s submitted, %(not_submitted)s/%(total)s "
                                  "did not submit, %(not_responding)s/%(total)s did not reply")
REMINDER_MONTHLY_SOH_SUMMARY = ("SOH - %(submitted)s/%(total)s reported, %(not_responding)s/%(total)s "
                                "did not reply")
REMINDER_MONTHLY_DELIVERY_SUMMARY = ("Deliveries - %(received)s/%(total)s received, %(not_received)s/%(total)s "
                                     "did not receive, %(not_responding)s/%(total)s did not reply")


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
        SupplyPointStatus.objects.create(supply_point=supply_point_id,
                                         status_type=type,
                                         status_value=value,
                                         status_date=now)
