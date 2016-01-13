from functools import partial
from corehq.apps.change_feed import topics
from dimagi.utils.dates import force_to_datetime
import fluff
from corehq.fluff.calculators.case import CasePropertyFilter
from custom.world_vision import WORLD_VISION_DOMAINS
from corehq.apps.users.models import CommCareUser, CommCareCase
from custom.utils.utils import flat_field
from custom.world_vision import user_calcs

from django.utils.dateformat import format


WV_DELETED_TYPES = ('CommCareCase-Deleted', )


class WorldVisionMotherFluff(fluff.IndicatorDocument):
    def case_property(property):
        return flat_field(lambda case: case.get_case_property(property))

    document_class = CommCareCase
    document_filter = CasePropertyFilter(type='ttc_mother')
    deleted_types = WV_DELETED_TYPES

    domains = WORLD_VISION_DOMAINS
    group_by = ('domain', 'user_id')
    save_direct_to_sql = True
    kafka_topic = topics.CASE

    name = flat_field(lambda case: case.name)
    lvl_4 = case_property('phc')
    lvl_3 = case_property('block')
    lvl_2 = case_property('district')
    lvl_1 = case_property('state')
    reason_for_mother_closure = flat_field(lambda case: case.reason_for_mother_closure if hasattr(case, 'reason_for_mother_closure')
                                                                                          and case.reason_for_mother_closure else 'unknown')
    mother_state = case_property('mother_state')
    fp_method = case_property('fp_method')

    anc_1 = case_property('anc_1')
    anc_2 = case_property('anc_2')
    anc_3 = case_property('anc_3')
    anc_4 = case_property('anc_4')
    tt_1 = case_property('tt_1')
    tt_2 = case_property('tt_2')
    tt_booster = case_property('tt_booster')
    iron_folic = case_property('iron_folic')
    completed_100_ifa = case_property('completed_100_ifa')
    anemia_signs = case_property('anemia_signs')
    currently_referred = case_property('currently_referred')
    knows_closest_facility = case_property('knows_closest_facility')
    edd = case_property('edd')
    previous_tetanus = case_property('previous_tetanus')
    pp_1_done = case_property('pp_1_done')
    pp_2_done = case_property('pp_2_done')
    pp_3_done = case_property('pp_3_done')
    pp_4_done = case_property('pp_4_done')
    delivery_date = case_property('delivery_date')
    cause_of_death_maternal = case_property('cause_of_death_maternal')
    place_of_birth = case_property('place_of_birth')
    birth_attendant_during_delivery = case_property('birth_attendant_during_delivery')
    type_of_delivery = case_property('type_of_delivery')
    date_of_mother_death = case_property('date_of_mother_death')

    number_of_children = user_calcs.NumberChildren()
    number_of_boys = user_calcs.NumberBoys()
    number_of_girls = user_calcs.NumberGirls()
    number_of_children_born_dead = user_calcs.StillBirth()

    opened_on = flat_field(lambda case: case.opened_on.date() if case.opened_on else None)
    closed_on = flat_field(lambda case: case.closed_on.date() if case.closed_on else None)

    women_registered = user_calcs.MotherRegistered()


def referenced_case_attribute(case, field_name):
    if not case.indices[0]['referenced_id']:
        return ""
    referenced_case = CommCareCase.get(case.indices[0]['referenced_id'])
    if hasattr(referenced_case, field_name):
        return getattr(referenced_case, field_name)
    else:
        return ""


def get_datepart(case, t='n'):
    child_date_of_death = case.get_case_property('child_date_of_death')
    if child_date_of_death:
        return format(force_to_datetime(child_date_of_death), t)
    else:
        return ""


def calculate_weight(case):
    weight_birth = case.get_case_property('weight_birth')
    if weight_birth:
        #Probably measured in grams. Should be converted to kilograms
        if float(weight_birth) > 10:
            return str(float(weight_birth) / 1000.0)
        else:
            return weight_birth
    return ""

# This calculator is necessary to generate 'date' field which is required in the database
class Numerator(fluff.Calculator):
    @fluff.null_emitter
    def numerator(self, case):
        yield None

class WorldVisionHierarchyFluff(fluff.IndicatorDocument):
    def user_data(property):
        """
        returns a flat field with a callable looking for `property` on the user
        """
        return flat_field(lambda user: user.user_data.get(property))

    document_class = CommCareUser
    domains = WORLD_VISION_DOMAINS
    group_by = ('domain',)
    save_direct_to_sql = True
    kafka_topic = topics.META

    numerator = Numerator()
    lvl_4 = user_data('phc')
    lvl_3 = user_data('block')
    lvl_2 = user_data('district')
    lvl_1 = user_data('state')



class WorldVisionChildFluff(fluff.IndicatorDocument):
    def case_property(property):
        return flat_field(lambda case: case.get_case_property(property))

    document_class = CommCareCase
    document_filter = CasePropertyFilter(type='ttc_child')
    deleted_types = WV_DELETED_TYPES

    domains = WORLD_VISION_DOMAINS
    group_by = ('domain', 'user_id')
    save_direct_to_sql = True
    kafka_topic = topics.CASE

    name = flat_field(lambda case: case.name)
    mother_id = flat_field(lambda case: case.indices[0]['referenced_id'])
    lvl_4 = flat_field(partial(referenced_case_attribute, field_name='phc'))
    lvl_3 = flat_field(partial(referenced_case_attribute, field_name='block'))
    lvl_2 = flat_field(partial(referenced_case_attribute, field_name='district'))
    lvl_1 = flat_field(partial(referenced_case_attribute, field_name='state'))

    reason_for_child_closure = case_property('reason_for_child_closure')
    bcg = case_property('bcg')
    opv0 = case_property('opv0')
    hepb0 = case_property('hepb0')
    opv1 = case_property('opv1')
    hepb1 = case_property('hepb1')
    dpt1 = case_property('dpt1')
    opv2 = case_property('opv2')
    hepb2 = case_property('hepb2')
    dpt2 = case_property('dpt2')
    opv3 = case_property('opv3')
    hepb3 = case_property('hepb3')
    dpt3 = case_property('dpt3')
    measles = case_property('measles')
    vita1 = case_property('vita1')
    vita2 = case_property('vita2')
    dpt_opv_booster = case_property('dpt_opv_booster')
    vita3 = case_property('vita3')
    type_of_child_death = case_property('type_of_child_death')
    cause_of_death_child = case_property('cause_of_death_child')
    pneumonia_since_last_visit = case_property('pneumonia_since_last_visit')
    has_diarrhea_since_last_visit = case_property('has_diarrhea_since_last_visit')
    dairrhea_treated_with_ors = case_property('dairrhea_treated_with_ors')
    dairrhea_treated_with_zinc = case_property('dairrhea_treated_with_zinc')
    weight_birth = flat_field(calculate_weight)
    breastfeed_1_hour = case_property('breastfeed_1_hour')
    exclusive_breastfeeding = case_property('exclusive_breastfeeding')
    comp_breastfeeding = case_property('comp_breastfeeding')
    supplementary_feeding_baby = case_property('supplementary_feeding_baby')
    deworm = case_property('deworm')
    ebf_stop_age_month = case_property('ebf_stop_age_month')
    gender = case_property('gender')

    opened_on = flat_field(lambda case: case.opened_on)
    closed_on = flat_field(lambda case: case.closed_on)
    dob = flat_field(lambda case: case.dob)
    date_of_death = case_property('child_date_of_death')
    month_of_death = flat_field(get_datepart)
    year_of_death = flat_field(partial(get_datepart, t='Y'))

    women_registered = user_calcs.ChildRegistered()


WorldVisionMotherFluffPillow = WorldVisionMotherFluff.pillow()
WorldVisionChildFluffPillow = WorldVisionChildFluff.pillow()
WorldVisionHierarchyFluffPillow = WorldVisionHierarchyFluff.pillow()
