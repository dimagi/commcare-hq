"""
Fluff IndicatorDocument definitions for the OPM reports.
"""
from corehq.fluff.calculators.case import CasePropertyFilter
from fluff.filters import CustomFilter
from corehq.apps.users.models import CommCareUser, CommCareCase
from couchforms.models import XFormInstance
from .constants import *
import fluff

from . import case_calcs, user_calcs

# OpmCaseFluff and OpmUserFluff are unusual in that they store only
# flat information about a specific case or user - no aggregation will
# be performed
from custom.utils.utils import flat_field

# This calculator is necessary to generate 'date' field which is required in the database
class Numerator(fluff.Calculator):
    @fluff.null_emitter
    def numerator(self, doc):
        yield None


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

    save_direct_to_sql = True

    name = flat_field(lambda user: user.name)

    numerator = Numerator()
    awc_code = user_data('awc_code')
    bank_name = user_data('bank_name')
    ifs_code = user_data('ifs_code')
    account_number = user_data('account_number')
    awc = user_data('awc')
    block = user_data('block')
    gp = user_data('gp')
    village = user_data('village')


def _get_case_id(form):
    case = form.form.get('case', {})
    if hasattr(case, 'get'):
        return case.get('@case_id')


# This is a more typical fluff doc, storing arbitrary info pulled from forms.
# Some stuff only pertains to case level queries, others to user level
class OpmFormFluff(fluff.IndicatorDocument):
    document_class = XFormInstance

    domains = ('opm',)
    group_by = (
        'domain',
        fluff.AttributeGetter('case_id', _get_case_id),
    )
    save_direct_to_sql = True

    name = flat_field(lambda form: form.name)

    # per user
    service_forms = user_calcs.ServiceForms()
    growth_monitoring = user_calcs.GrowthMonitoring()


class OpmHealthStatusAllInfoFluff(fluff.IndicatorDocument):

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


class OPMHierarchyFluff(fluff.IndicatorDocument):
    def user_data(property):
        """
        returns a flat field with a callable looking for `property` on the user
        """
        return flat_field(lambda user: user.user_data.get(property))

    document_class = CommCareUser
    domains = ('opm',)
    group_by = ('domain',)

    save_direct_to_sql = True
    numerator = Numerator()
    block = user_data('block')
    gp = user_data('gp')
    awc = user_data('awc')


class VhndAvailabilityFluff(fluff.IndicatorDocument):

    document_class = CommCareCase
    domains = ('opm',)
    group_by = ('owner_id',)
    save_direct_to_sql = True
    document_filter = CasePropertyFilter(type='vhnd')

    vhnd = case_calcs.VhndAvailabilityCalc()


# These Pillows need to be added to the list of PILLOWTOPS in settings.py
OpmCaseFluffPillow = OpmCaseFluff.pillow()
OpmUserFluffPillow = OpmUserFluff.pillow()
OpmFormFluffPillow = OpmFormFluff.pillow()
OpmHealthStatusAllInfoFluffPillow = OpmHealthStatusAllInfoFluff.pillow()
VhndAvailabilityFluffPillow = VhndAvailabilityFluff.pillow()
OPMHierarchyFluffPillow = OPMHierarchyFluff.pillow()
