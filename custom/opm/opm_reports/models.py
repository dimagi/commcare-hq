from corehq.fluff.calculators.xform import IntegerPropertyReference
from couchforms.models import XFormInstance
from corehq.apps.users.models import CommCareUser, CommCareCase
import fluff
from corehq.fluff.calculators import xform as xcalculators
from . import calculations
from .beneficiary import Beneficiary
from .incentive import Worker


# put this in a get_dict_from(item) method in the parent class of Beneficiary and Worker
def get_item_data(model):
    def get_data(item):
        instance = model(item)
        return dict([
            (method, getattr(instance, method)) for method, _ in instance.method_map
        ])
    return get_data


class OpmCaseFluff(fluff.IndicatorDocument):
    document_class = CommCareCase

    domains = ('opm',)
    group_by = ['domain', 'owner_id']

    # all_pregnancies = calculations.AllPregnancies()

    bp1 = calculations.BirthPreparedness()

    # beneficiary_data = fluff.DictField(get_item_data(Beneficiary))

    name = fluff.FlatField(lambda case: case.name)
    awc_name = fluff.FlatField(lambda case: "AWC Name")
    bank_name = fluff.FlatField(lambda case: "AWW Bank Name")
    account_number = fluff.FlatField(lambda case: "AWW Bank Account Number")
    block = fluff.FlatField(lambda case: "Block Name")

    women_registered = "No. of women registered under BCSP"
    children_registered = "No. of children registered under BCSP"
    service_forms_count = "Submission of Service Availability form"
    growth_monitoring_count = "No. of Growth monitoring Sections Filled for eligible children"
    service_forms_cash = "Payment for Service Availability Form (in Rs.)"
    growth_monitoring_cash = "Payment for Growth Monitoring Forms (in Rs.)"
    month_total = "Total Payment Made for the month (in Rs.)"
    last_month_total = "Amount of AWW incentive paid last month"


class OpmUserFluff(fluff.IndicatorDocument):
    document_class = CommCareUser

    domains = ('opm',)
    group_by = ['domain', 'owner_id']

    something = "hello!"

    # incentive_data = fluff.DictField(get_item_data(Worker))


# OPMFluff.get_result('all_pregnancies', [domain, user_id])
OpmCasePillow = OpmCaseFluff.pillow()
OpmUserPillow = OpmUserFluff.pillow()
