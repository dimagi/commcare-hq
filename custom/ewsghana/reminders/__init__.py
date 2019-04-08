from __future__ import absolute_import
from __future__ import unicode_literals
from django.utils.translation import ugettext_lazy as _

REGISTER_HELP = _("Sorry, I didn't understand. To register, send register <name> <facility code>. "
                  "Example: register john dwdh'")
REGISTRATION_CONFIRM = _("Congratulations %(contact_name)s, you have successfully been "
                         "registered for the Early Warning System. Your facility is %(sdp_name)s")
REGISTER_MESSAGE = _("You must be registered on EWS before you can submit a stock report. "
                     "Please contact your DHIO or RHIO.")
NO_SUPPLY_POINT_MESSAGE = _("You are not associated with a facility. Please contact your DHIO or RHIO for help.")
REQ_SUBMITTED = _("Thank you for confirming you have submitted your RRIRV this month.")
REQ_NOT_SUBMITTED = _("Please submit your RRIRV as soon as possible.")
PRODUCTS_NOT_SUBMITTED = _("You have not submitted any product reports yet.")
SOH_HELP_MESSAGE = _("Please send in your stock on hand information in the format"
                     " 'soh <product> <amount> <product> <amount>...'")

DOMAIN = 'ews-ghana-test'
STOCK_ON_HAND_RESPONSIBILITY = 'reporter'
REPORTEE_RESPONSIBILITY = 'reportee'
STOCK_ON_HAND_REMINDER = 'Hi %(name)s! Please text your stock report tomorrow Friday by 2:00 pm. ' \
                         'Your stock report can help save lives.'
SECOND_STOCK_ON_HAND_REMINDER = 'Hi %(name)s, we did not receive your stock report last Friday. ' \
                                'Please text your stock report as soon as possible.'
SECOND_INCOMPLETE_SOH_REMINDER = 'Hi %(name)s, your facility is missing a few SMS stock reports. ' \
                                 'Please report on: %(products)s.'
THIRD_STOCK_ON_HAND_REMINDER = 'Dear %(name)s, %(facility)s has not reported its stock this week. ' \
                               'Please make sure that the SMS stock report is submitted.'
INCOMPLETE_SOH_TO_SUPER = 'Dear %(name)s, %(facility)s\'s SMS stock report was INCOMPLETE. ' \
                          'Please report for: %(products)s'
STOCKOUT_REPORT = 'Dear %(name)s, %(facility)s reported STOCKOUTS on %(date)s of %(products)s'
RRIRV_REMINDER = "Dear %(name)s, have you submitted your RRIRV forms this month? Please reply 'yes' or 'no'"
WEB_REMINDER = "Dear %(name)s, you have not visited commcarehq.org in a long time. " \
               "Please log in to find up-to-date info about stock availability and bottlenecks in Ghana."
RECEIPT_CONFIRM = 'Thank you, you reported receipts for %(products)s.'

ERROR_MESSAGE = 'Error! You submitted increases in stock levels of {products_list}' \
                ' without corresponding receipts. Please contact your DHIO or RHIO for assistance.'
