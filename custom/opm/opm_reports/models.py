from corehq.fluff.calculators.xform import IntegerPropertyReference
from couchforms.models import XFormInstance
from casexml.apps.case.models import CommCareCase
import fluff
from corehq.fluff.calculators import xform as xcalculators
from . import calculations

class OPMFluff(fluff.IndicatorDocument):
    document_class = CommCareCase

    domains = ('opm',)
    group_by = ['domain', 'owner_id']

    all_pregnancies = calculations.AllPregnancies()

    # bank_name = MetaData(lambda case: case.forms[])

# OPMFluff.get_result('all_pregnancies', [domain, user_id])
OPMFluffPillow = OPMFluff.pillow()