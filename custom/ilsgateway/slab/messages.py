from __future__ import absolute_import
from django.utils.translation import ugettext_lazy as _

REMINDER_TRANS = _("Did you receive or transfer stock to another facility last month?"
                   " Please reply either 'trans no' or 'trans yes'")
TRANS_HELP = _("You can respond 'trans yes' if you have received "
               "or transfered stock last month or 'trans no' if you have not")
SOH_OVERSTOCKED = _("You are overstocked for %(overstocked_list)s that you can redistribute to other facilities. "
                    "Keep %(products_list)s.")
REMINDER_STOCKOUT = _("You are stocked out of %(products_list)s."
                      " The following facilities are overstocked: %(overstocked_list)s")
