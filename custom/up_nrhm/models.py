from functools import partial
from couchforms.models import XFormInstance
from corehq.apps.users.models import CommCareUser
from corehq.fluff.calculators.xform import FormPropertyFilter
from custom.up_nrhm import ASHA_FUNCTIONALITY_CHECKLIST_XMLNS
from custom.up_nrhm.calculators import Numerator, PropertyCalculator
from custom.up_nrhm.utils import get_case_property, get_case_id
from custom.utils.utils import flat_field
import fluff


class UpNRHMLocationHierarchyFluff(fluff.IndicatorDocument):
    group_by = ('domain', )
    domains = ('up-nrhm', )

    document_class = CommCareUser
    district = flat_field(lambda user: user.user_data.get('district'))
    block = flat_field(lambda user: user.user_data.get('block'))
    user_id = flat_field(lambda user: user._id)
    username = flat_field(lambda user: user.full_name)
    numerator = Numerator()

    save_direct_to_sql = True


class ASHAFacilitatorsFluff(fluff.IndicatorDocument):
    group_by = ('domain', )
    domains = ('up-nrhm', )

    document_class = XFormInstance
    document_filter = FormPropertyFilter(
        xmlns=ASHA_FUNCTIONALITY_CHECKLIST_XMLNS
    )

    owner_id = flat_field(partial(get_case_property, property_name='owner_id'))
    case_id = flat_field(get_case_id)

    home_birth_last_month_visited = PropertyCalculator(property_name="home_birth_last_month_visited")
    hv_fx_newborns_visited = PropertyCalculator(property_name="hv_fx_newborns_visited")
    hv_fx_vhnd = PropertyCalculator(property_name="hv_fx_vhnd")
    hv_fx_support_inst_delivery = PropertyCalculator(property_name="hv_fx_support_inst_delivery")
    hv_fx_child_illness_mgmt = PropertyCalculator(property_name="hv_fx_child_illness_mgmt")
    hv_fx_nut_counseling = PropertyCalculator(property_name="hv_fx_nut_counseling")
    hv_fx_malaria = PropertyCalculator(property_name="hv_fx_malaria")
    hv_fx_dots = PropertyCalculator(property_name="hv_fx_dots")
    hv_fx_fp = PropertyCalculator(property_name="hv_fx_fp")
    hv_percent_functionality = PropertyCalculator(property_name="hv_percent_functionality")

    save_direct_to_sql = True

UpNRHMLocationHierarchyFluffPillow = UpNRHMLocationHierarchyFluff.pillow()
ASHAFacilitatorsFluffPillow = ASHAFacilitatorsFluff.pillow()
