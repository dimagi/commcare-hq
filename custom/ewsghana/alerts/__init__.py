from django.utils.translation import ugettext as _

DOMAIN = 'ewsghana-test-1'

ONGOING_NON_REPORTING = 'SMS report MISSING from these facilities over the past 3 weeks! Please follow up:\n%s '
ONGOING_STOCKOUT_AT_SDP = 'Ongoing STOCKOUTS at these facilities over the past 3 weeks! Please follow up:\n%s'
ONGOING_STOCKOUT_AT_RMS = 'Ongoing STOCKOUTS at these RMS over the past 3 weeks! Please follow up:\n%s '
URGENT_STOCKOUT = 'URGENT STOCKOUT: More than half of the facilities reporting to EWS in %s are experiencing stockouts of one or more of: %s.'
URGENT_NON_REPORTING = 'URGENT NON-REPORTING: More than half of the facilities registered to EWS in %s have not reported for the past month. Please log in to http://ewsghana.com for details.'
WEB_REMINDER = 'Dear %s, you have not visited ewsghana.com in a long time. Please log in to find up-to-date info about stock availability and bottlenecks in Ghana.'
REPORT_REMINDER = 'Dear %s, %s has not reported its stock this week. Please make sure that the SMS stock report is submitted. '
INCOMPLETE_REPORT = 'Dear Name, (name of facility) SMS stock report was INCOMPLETE. Please report for: (indicate the non-reported commodities in full. Eg.Copper-T, Jadelle, Depo Provera, Norigynon, Microlut, Male Condom, Micro-G, etc)'
COMPLETE_REPORT = 'Thank you for submitting your report for the week.'
BELOW_REORDER_LEVELS = 'Dear %s, the following commodities are at or below re-order level at the %s. %s'
ABOVE_THRESHOLD = 'Dear %s, these items are overstocked: %s. The district admin has been informed.'
WITHOUT_RECEIPTS = 'Error! You submitted increases in stock levels of %s without corresponding receipts. Please contact your DHIO or RHIO for assistance.'

