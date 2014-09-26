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

    opened_on = flat_field(lambda case: case.opened_on)
    closed_on = flat_field(lambda case: case.closed_on)
    lmp = case_property('lmp')
    mother_state = case_property('mother_state')

    women_registered = user_calcs.MotherRegistered()

WorldVisionMotherFluffPillow = WorldVisionMotherFluff.pillow()
