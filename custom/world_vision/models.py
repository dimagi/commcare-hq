import fluff
from corehq.fluff.calculators.case import CasePropertyFilter
from custom.world_vision import WORLD_VISION_DOMAINS
from corehq.apps.users.models import CommCareCase
from custom.utils.utils import flat_field
from custom.world_vision.reports import user_calcs


class WorldVisionMotherFluff(fluff.IndicatorDocument):
    def case_property(property):
        return flat_field(lambda case: case.get_case_property(property))

    document_class = CommCareCase
    document_filter = CasePropertyFilter(type='ttc_mother')

    domains = WORLD_VISION_DOMAINS
    group_by = ('domain', 'user_id')
    save_direct_to_sql = True

    name = flat_field(lambda case: case.name)
    phc = case_property('phc')
    block = case_property('block')
    district = case_property('district')
    state = case_property('state')
    reason_for_mother_closure = case_property('reason_for_mother_closure')
    mother_state = case_property('mother_state')

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
    lmp = case_property('lmp')
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

    number_of_children = user_calcs.NumberChildren()
    number_of_boys = user_calcs.NumberBoys()
    number_of_girls = user_calcs.NumberGirls()
    number_of_children_born_dead = user_calcs.StillBirth()

    opened_on = flat_field(lambda case: case.opened_on)
    closed_on = flat_field(lambda case: case.closed_on)

    women_registered = user_calcs.MotherRegistered()

class WorldVisionChildFluff(fluff.IndicatorDocument):
    def case_property(property):
        return flat_field(lambda case: case.get_case_property(property))

    document_class = CommCareCase
    document_filter = CasePropertyFilter(type='ttc_child')

    domains = WORLD_VISION_DOMAINS
    group_by = ('domain', 'user_id')
    save_direct_to_sql = True

    name = flat_field(lambda case: case.name)
    phc = flat_field(lambda case: CommCareCase.get(case.indices[0]['referenced_id']).phc \
        if hasattr(CommCareCase.get(case.indices[0]['referenced_id']), 'phc') else '')
    block = flat_field(lambda case: CommCareCase.get(case.indices[0]['referenced_id']).block \
        if hasattr(CommCareCase.get(case.indices[0]['referenced_id']), 'block') else '')
    district = flat_field(lambda case: CommCareCase.get(case.indices[0]['referenced_id']).district \
        if hasattr(CommCareCase.get(case.indices[0]['referenced_id']), 'district') else '')
    state = flat_field(lambda case: CommCareCase.get(case.indices[0]['referenced_id']).state \
        if hasattr(CommCareCase.get(case.indices[0]['referenced_id']), 'state') else '')

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

    opened_on = flat_field(lambda case: case.opened_on)
    closed_on = flat_field(lambda case: case.closed_on)
    dob = flat_field(lambda case: case.dob)

    women_registered = user_calcs.ChildRegistered()


WorldVisionMotherFluffPillow = WorldVisionMotherFluff.pillow()
WorldVisionChildFluffPillow = WorldVisionChildFluff.pillow()
