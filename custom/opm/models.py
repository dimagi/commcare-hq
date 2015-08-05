"""
Fluff IndicatorDocument definitions for the OPM reports.
"""
from corehq.fluff.calculators.case import CasePropertyFilter
from fluff.filters import CustomFilter
from corehq.apps.users.models import CommCareUser, CommCareCase
from couchforms.models import XFormInstance
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
    edd = case_property('edd')
    dod = case_property('dod')

    opened_on = flat_field(lambda case: case.opened_on)
    closed_on = flat_field(lambda case: case.closed_on)
    # Okay, I lied, there's one aggregated field:
    women_registered = user_calcs.WomenRegistered()
    children_registered = user_calcs.ChildrenRegistered()


def is_valid_user(user):
    if not (user.is_active and user.base_doc == "CouchUser"):
        return False
    for key in ('awc', 'gp', 'block'):
        if not user.user_data.get(key, False):
            return False
    return True


class OpmUserFluff(fluff.IndicatorDocument):
    def user_data(property):
        """
        returns a flat field with a callable looking for `property` on the user
        """
        return flat_field(lambda user: user.user_data.get(property))

    document_class = CommCareUser
    domains = ('opm',)
    group_by = ('domain', )
    # Only consider active users
    document_filter = CustomFilter(is_valid_user)

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
    gps = user_data('gps')


def _get_user_id(form):
    case = form.form.get('case', {})
    if hasattr(case, 'get'):
        return case.get('@user_id')


# This is a more typical fluff doc, storing arbitrary info pulled from forms.
# Some stuff only pertains to case level queries, others to user level
class OpmFormFluff(fluff.IndicatorDocument):
    document_class = XFormInstance

    domains = ('opm',)
    group_by = (
        'domain',
        fluff.AttributeGetter('user_id', _get_user_id),
    )
    save_direct_to_sql = True

    name = flat_field(lambda form: form.name)

    # per user
    service_forms = user_calcs.ServiceForms()
    growth_monitoring = user_calcs.GrowthMonitoring()


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
VhndAvailabilityFluffPillow = VhndAvailabilityFluff.pillow()
