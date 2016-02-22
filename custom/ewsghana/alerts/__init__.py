from django.utils.translation import ugettext as _

ONGOING_NON_REPORTING = _('SMS report MISSING from these facilities over the past 3 weeks! Please follow up:\n%s')
ONGOING_STOCKOUT_AT_SDP = _('Ongoing STOCKOUTS at these facilities over the past 3 weeks! Please follow up:\n%s')
ONGOING_STOCKOUT_AT_RMS = _('Ongoing STOCKOUTS at these RMS over the past 3 weeks! Please follow up:\n%s ')
URGENT_STOCKOUT = _('URGENT STOCKOUT: More than half of the facilities reporting to EWS in %(location)s '
                    'are experiencing stockouts of one or more of: %(products)s.')
URGENT_NON_REPORTING = _('URGENT NON-REPORTING: More than half of the facilities registered to EWS in %s '
                         'have not reported for the past month. Please log in to http://ewsghana.com for details.')
WEB_REMINDER = _('Dear %s, you have not visited ewsghana.com in a long time. '
                 'Please log in to find up-to-date info about stock availability and bottlenecks in Ghana.')
COMPLETE_REPORT = _('Dear %s, thank you for reporting the commodities you have in stock.')
WITHOUT_RECEIPTS = _('Error! You submitted increases in stock levels of %s '
                     'without corresponding receipts. Please contact your DHIO or RHIO for assistance.')

STOCKOUTS_MESSAGE = _('these items are stocked out: %(products)s.')
REORDER_MESSAGE = _('Please order %s.')
LOW_SUPPLY_MESSAGE = _('these items need to be reordered: %(low_supply)s.')
OVERSTOCKED_MESSAGE = _('these items are overstocked: %(overstocked)s. The district admin has been informed.')
RECEIPT_MESSAGE = _('Dear %(username)s, thank you for reporting the commodities you have. '
                    'You received %(received)s.')
