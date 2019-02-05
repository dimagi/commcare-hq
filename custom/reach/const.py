from __future__ import absolute_import
from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy as _

INDICATOR_LIST = {
    'registered_eligible_couples': _('Registered Eligible Couples'),
    'registered_pregnancies': _('Registered Pregnancies'),
    'registered_children': _('Registered Children'),
    'couples_family_planning': _('Couples using Family Planning Method'),
    'high_risk_pregnancies': _('High Risk Pregnancies'),
    'institutional_deliveries': _('Institutional Deliveries'),
}

NUMERIC = 'numeric'
PERCENT = 'percent'

COLORS = {
    'violet': '#725CA4',
    'blue': '#04AEE6',
    'mediumblue': '#004EBC',
    'aqua': '#1CC6CC',
    'orange': '#F5BB5D',
    'darkorange': '#FF8300',
}
