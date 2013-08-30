from corehq.apps.users.models import CommCareUser, CommCareCase
from corehq.fluff.calculators.xform import IntegerPropertyReference
from corehq.fluff.calculators import xform as xcalculators

from couchforms.models import XFormInstance
import fluff

from . import case_calcs, user_calcs


# OpmCaseFluff and OpmUserFluff are unusual in that they store only
# flat information about a specific case or user - no aggregation will
# be performed
class OpmCaseFluff(fluff.IndicatorDocument):
    def case_property(property):
        """
        returns a flat field with a callable looking for `property` on the case
        """
        return fluff.FlatField(lambda case: case.get_case_property(property))

    document_class = CommCareCase
    domains = ('opm',)
    group_by = ('domain', )

    name = fluff.FlatField(lambda case: case.name)
    awc_name = case_property("awc_name")
    bank_name = case_property("bank_name")
    account_number = case_property("bank_account_number")
    block = case_property("block_name")
    village = case_property("village_name")


class OpmUserFluff(fluff.IndicatorDocument):
    def user_data(property):
        """
        returns a flat field with a callable looking for `property` on the user
        """
        return fluff.FlatField(lambda user: user.user_data.get(property))
    
    document_class = CommCareUser
    domains = ('opm',)
    group_by = ('domain', )

    name = fluff.FlatField(lambda user: user.name)
    awc_name = user_data('awc')
    bank_name = user_data('bank_name')
    account_number = user_data('account_number')
    block = user_data('block')
    village = user_data('village')


# This is a more typical fluff doc, storing arbitrary info pulled from forms.
# Some stuff only pertains to case level queries, others to user level
class OpmFormFluff(fluff.IndicatorDocument):
    # def wrap(self, data):
    #     if isinstance(data.get('child_spacing'), basestring):
    #         del data['child_spacing']
    #     super(OpmFormFluff, self).wrap(data)

    document_class = XFormInstance

    domains = ('opm',)
    # group_by = ('domain', )

    name = fluff.FlatField(lambda form: form.name)

    # per case
    bp1_cash = case_calcs.BirthPreparedness(
        ['window_1_1', 'window_1_2', 'window_1_3'])
    bp2_cash = case_calcs.BirthPreparedness(
        ['window_2_1', 'window_2_2', 'window_2_3'])
    delivery = case_calcs.Delivery()
    child_followup = "Child Followup Form"
    child_spacing = case_calcs.ChildSpacing()
    # total = "Amount to be paid to beneficiary"

    # per user
    women_registered = "No. of women registered under BCSP"
    # women_registered = user_calcs.WomenRegistered()
    children_registered = "No. of children registered under BCSP"
    service_forms_count = "Submission of Service Availability form"
    growth_monitoring_count = "No. of Growth monitoring Sections Filled for eligible children"
    service_forms = "Payment for Service Availability Form (in Rs.)"
    growth_monitoring = "Payment for Growth Monitoring Forms (in Rs.)"
    # month_total = "Total Payment Made for the month (in Rs.)"
    # last_month_total = "Amount of AWW incentive paid last month"


# OPMFluff.get_result('all_pregnancies', [domain, user_id])

OpmCasePillow = OpmCaseFluff.pillow()
OpmUserPillow = OpmUserFluff.pillow()
OpmFormPillow = OpmFormFluff.pillow()
