"""
Fluff IndicatorDocument definitions for the OPM reports.
"""
from corehq.apps.users.models import CommCareUser, CommCareCase
from couchforms.models import XFormInstance
import fluff

from . import case_calcs, user_calcs


def flat_field(fn):
    def getter(item):
        return unicode(fn(item) or "")
    return fluff.FlatField(getter)


# OpmCaseFluff and OpmUserFluff are unusual in that they store only
# flat information about a specific case or user - no aggregation will
# be performed
class OpmCaseFluff(fluff.IndicatorDocument):
    def case_property(property):
        """
        returns a flat field with a callable looking for `property` on the case
        """
        return flat_field(lambda case: case.get_case_property(property))

    document_class = CommCareCase
    domains = ('opm',)
    group_by = ('domain', 'user_id')

    name = flat_field(lambda case: case.name)
    husband_name = case_property('husband_name')
    awc_name = case_property('awc_name')
    bank_name = case_property('bank_name')
    bank_branch_name = case_property('bank_branch_name')
    bank_branch_code = case_property('bank_branch_code')
    account_number = case_property('bank_account_number')
    block = case_property('block_name')
    village = case_property('village_name')

    # Okay, I lied, there's one aggregated field:
    women_registered = user_calcs.WomenRegistered()


class OpmUserFluff(fluff.IndicatorDocument):
    def user_data(property):
        """
        returns a flat field with a callable looking for `property` on the user
        """
        return flat_field(lambda user: user.user_data.get(property))
    
    document_class = CommCareUser
    domains = ('opm',)
    group_by = ('domain', )

    name = flat_field(lambda user: user.name)
    awc_name = user_data('awc')
    bank_name = user_data('bank_name')
    account_number = user_data('account_number')
    block = user_data('block')
    village = user_data('village')


# This is a more typical fluff doc, storing arbitrary info pulled from forms.
# Some stuff only pertains to case level queries, others to user level
class OpmFormFluff(fluff.IndicatorDocument):
    document_class = XFormInstance

    domains = ('opm',)
    group_by = (
        'domain',
        fluff.AttributeGetter('case_id', lambda form: form.form['case']['@case_id']),
    )

    name = flat_field(lambda form: form.name)

    # per case
    bp1_cash = case_calcs.BirthPreparedness(
        ['window_1_1', 'window_1_2', 'window_1_3'])
    bp2_cash = case_calcs.BirthPreparedness(
        ['window_2_1', 'window_2_2', 'window_2_3'])
    delivery = case_calcs.Delivery()
    child_followup = case_calcs.ChildFollowup()
    child_spacing = case_calcs.ChildSpacing()

    # per user
    service_forms = user_calcs.ServiceForms()
    growth_monitoring = user_calcs.GrowthMonitoring()

class OpmHealthStatusFluff(fluff.IndicatorDocument):

    def case_property(property):
        """
        returns a flat field with a callable looking for `property` on the case
        """
        return flat_field(lambda case: case.get_case_property(property))

    document_class = CommCareCase
    domains = ('opm',)
    group_by = ('domain', 'user_id')

    name = flat_field(lambda case: case.name)
    awc_name = case_property('awc_name')
    account_number = case_property('bank_account_number')
    block = case_property('block_name')

    #aggregated field
    lmp = case_calcs.Lmp()
    lactating = case_calcs.Lactating()
    children = case_calcs.LiveChildren()
    vhnd_monthly = case_calcs.VhndMonthly()
    ifa_tablets = case_calcs.IfaTablets()

# These Pillows need to be added to the list of PILLOWTOPS in settings.py
OpmCaseFluffPillow = OpmCaseFluff.pillow()
OpmUserFluffPillow = OpmUserFluff.pillow()
OpmFormFluffPillow = OpmFormFluff.pillow()
OpmHealthStatusFluffPillow = OpmHealthStatusFluff.pillow()
