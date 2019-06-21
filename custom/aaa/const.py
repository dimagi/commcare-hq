from __future__ import absolute_import
from __future__ import unicode_literals

from django.utils.translation import ugettext_noop as _

from corehq.const import ONE_DAY

BLOB_EXPIRATION_TIME = ONE_DAY

INDICATOR_LIST = {
    'registered_eligible_couples': _('Registered Eligible Couples'),
    'registered_pregnancies': _('Registered Pregnancies'),
    'registered_children': _('Registered Children'),
    'couples_family_planning': _('Couples using Family Planning Method'),
    'high_risk_pregnancies': _('High Risk Pregnancies'),
    'institutional_deliveries': _('Institutional Deliveries'),
}

MINISTRY_MOHFW = 'MoHFW'
MINISTRY_MWCD = 'MWCD'

ALL = 'ALL'

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

PRODUCT_CODES = [
    "1g_bcg",
    "1g_dpt_1",
    "2g_dpt_2",
    "3g_dpt_3",
    "5g_dpt_booster",
    "5g_dpt_booster1",
    "7gdpt_booster_2",
    "0g_hep_b_0",
    "1g_hep_b_1",
    "2g_hep_b_2",
    "3g_hep_b_3",
    "3g_ipv",
    "4g_je_1",
    "5g_je_2",
    "5g_measles_booster",
    "4g_measles",
    "0g_opv_0",
    "1g_opv_1",
    "2g_opv_2",
    "3g_opv_3",
    "5g_opv_booster",
    "1g_penta_1",
    "2g_penta_2",
    "3g_penta_3",
    "1g_rv_1",
    "2g_rv_2",
    "3g_rv_3",
    "4g_vit_a_1",
    "5g_vit_a_2",
    "6g_vit_a_3",
    "6g_vit_a_4",
    "6g_vit_a_5",
    "6g_vit_a_6",
    "6g_vit_a_7",
    "6g_vit_a_8",
    "7g_vit_a_9",
    "anc_1",
    "anc_2",
    "anc_3",
    "anc_4",
    "tt_1",
    "tt_2",
    "tt_booster",
]
