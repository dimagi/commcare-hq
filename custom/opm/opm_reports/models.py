from corehq.fluff.calculators.xform import IntegerPropertyReference
from couchforms.models import XFormInstance
from casexml.apps.case.models import CommCareCase
import fluff
from corehq.fluff.calculators import xform as xcalculators
from . import calculations

class OpmCaseFluff(fluff.IndicatorDocument):
    document_class = CommCareCase

    domains = ('opm',)
    group_by = ['domain', 'owner_id']

    all_pregnancies = calculations.AllPregnancies()

    name = fluff.StringField(lambda case: case.name)
    awc_name = "AWC Name"
    bank_name = "Bank Name"
    account_number = fluff.StringField(lambda case:
        case.get_case_property('bank_account_number') or "")
    block = "Block Name"
    village = "Village Name"
    bp1_cash = "Birth Preparedness Form 1"
    bp2_cash = "Birth Preparedness Form 2"
    delivery_cash = "Delivery Form"
    child_cash = "Child Followup Form"
    spacing_cash = "Birth Spacing Bonus"
    total = "Amount to be paid to beneficiary"


    # bank_name = MetaData(lambda case: case.forms[])

# OPMFluff.get_result('all_pregnancies', [domain, user_id])
OPMFluffPillow = OpmCaseFluff.pillow()
