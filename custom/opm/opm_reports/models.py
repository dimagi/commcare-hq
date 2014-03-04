"""
Fluff IndicatorDocument definitions for the OPM reports.
"""
from corehq.apps.users.models import CommCareUser, CommCareCase
from couchforms.models import XFormInstance
from custom.opm.opm_reports.constants import CFU1_XMLNS
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
    save_direct_to_sql = True

    name = flat_field(lambda case: case.name)
    husband_name = case_property('husband_name')
    awc_name = case_property('awc_name')
    bank_name = case_property('bank_name')
    bank_branch_name = case_property('bank_branch_name')
    ifs_code = case_property('ifs_code')
    account_number = case_property('bank_account_number')
    block = case_property('block_name')
    village = case_property('village_name')

    opened_on = flat_field(lambda case: case.opened_on)
    closed_on = flat_field(lambda case: case.closed_on)
    # Okay, I lied, there's one aggregated field:
    women_registered = user_calcs.WomenRegistered()
    children_registered = user_calcs.ChildrenRegistered()


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
    save_direct_to_sql = True

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


class OpmHealthStatusBasicInfoFluff(fluff.IndicatorDocument):

    document_class = CommCareCase
    domains = ('opm',)
    group_by = ('domain', 'user_id')
    save_direct_to_sql = True


    opened_on = flat_field(lambda case: case.opened_on)
    closed_on = flat_field(lambda case: case.closed_on)

    beneficiaries_registered = user_calcs.WomenRegistered()
    lmp = case_calcs.Lmp()
    lactating = case_calcs.Lactating()
    children = case_calcs.LiveChildren()


class OpmHealthStatusFluff(fluff.IndicatorDocument):

    document_class = CommCareCase
    domains = ('opm',)
    group_by = ('domain', 'user_id')
    save_direct_to_sql = True

    #aggregated field
    vhnd_monthly = case_calcs.VhndMonthly()
    ifa_tablets = case_calcs.IfaTablets()
    weight_once = case_calcs.Weight()
    weight_twice = case_calcs.Weight(count=1)
    children_monitored_at_birth = case_calcs.ChildrenInfo(prop='child%s_child_weight', num_in_condition='exist', forms=[CFU1_XMLNS])
    children_registered = case_calcs.ChildrenInfo(prop='child%s_child_register', num_in_condition='exist', forms=[CFU1_XMLNS])
    growth_monitoring_session_1 = case_calcs.ChildrenInfo(prop='child%s_child_growthmon')
    growth_monitoring_session_2 = case_calcs.ChildrenInfo(prop='child%s_child_growthmon', num_in_condition=1)
    growth_monitoring_session_3 = case_calcs.ChildrenInfo(prop='child%s_child_growthmon', num_in_condition=2)
    growth_monitoring_session_4 = case_calcs.ChildrenInfo(prop='child%s_child_growthmon', num_in_condition=3)
    growth_monitoring_session_5 = case_calcs.ChildrenInfo(prop='child%s_child_growthmon', num_in_condition=4)
    growth_monitoring_session_6 = case_calcs.ChildrenInfo(prop='child%s_child_growthmon', num_in_condition=5)
    growth_monitoring_session_7 = case_calcs.ChildrenInfo(prop='child%s_child_growthmon', num_in_condition=6)
    growth_monitoring_session_8 = case_calcs.ChildrenInfo(prop='child%s_child_growthmon', num_in_condition=7)
    growth_monitoring_session_9 = case_calcs.ChildrenInfo(prop='child%s_child_growthmon', num_in_condition=8)
    growth_monitoring_session_10 = case_calcs.ChildrenInfo(prop='child%s_child_growthmon', num_in_condition=9)
    growth_monitoring_session_11 = case_calcs.ChildrenInfo(prop='child%s_child_growthmon', num_in_condition=10)
    growth_monitoring_session_12 = case_calcs.ChildrenInfo(prop='child%s_child_growthmon', num_in_condition=11)
    nutritional_status_normal = case_calcs.Status(status='NORMAL')
    nutritional_status_mam = case_calcs.Status(status='MAM')
    nutritional_status_sam = case_calcs.Status(status='SAM')
    treated = case_calcs.ChildrenInfo(prop='child%s_child_orszntreat')
    suffering = case_calcs.ChildrenInfo(prop='child%s_suffer_diarrhea')
    excbreastfed = case_calcs.BreastFed()
    measlesvacc = case_calcs.ChildrenInfo(prop='child%s_child_measlesvacc')

# These Pillows need to be added to the list of PILLOWTOPS in settings.py
OpmCaseFluffPillow = OpmCaseFluff.pillow()
OpmUserFluffPillow = OpmUserFluff.pillow()
OpmFormFluffPillow = OpmFormFluff.pillow()
OpmHealthStatusBasicInfoFluffPillow = OpmHealthStatusBasicInfoFluff.pillow()
OpmHealthStatusFluffPillow = OpmHealthStatusFluff.pillow()
