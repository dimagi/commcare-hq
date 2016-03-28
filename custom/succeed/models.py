# Stub models file
from corehq.apps.change_feed import topics
from dimagi.ext.couchdbkit import Document
# ensure our signals get loaded at django bootstrap time
from . import signals
from corehq.apps.users.models import CommCareCase
from custom.succeed.reports import VISIT_SCHEDULE, LAST_INTERACTION_LIST, PM3
import fluff
from custom.utils.utils import flat_field
from fluff.filters import CustomFilter


LAST_VISIT = {
    'visit_name': 'last',
    'days': -1
}


class _(Document):
    pass


def get_randomization_date(case):
    return case['randomization_date']


def get_next_visit(case):
    actions = list(case['actions'])
    next_visit = VISIT_SCHEDULE[0]
    for visit_key, visit in enumerate(VISIT_SCHEDULE):
        is_ignored = case.get_case_property(visit['ignored_field'])
        completed = case.get_case_property(visit['completion_field'])
        if completed != '' and is_ignored is not None and is_ignored.lower() == 'yes':
            try:
                next_visit = VISIT_SCHEDULE[visit_key + 1]
            except IndexError:
                next_visit = LAST_VISIT
        else:
            for key, action in enumerate(actions):
                if visit['xmlns'] == action['xform_xmlns']:
                    try:
                        next_visit = VISIT_SCHEDULE[visit_key + 1]
                        del actions[key]
                        break
                    except IndexError:
                        next_visit = LAST_VISIT
    return next_visit


def visit_name(case):
    next_visit = get_next_visit(case)
    return next_visit['visit_name']


def visit_days(case):
    next_visit = get_next_visit(case)
    return next_visit['days']


def is_active(case):
    active = 'True'
    for action in case['actions']:
        if PM3 == action['xform_xmlns']:
            active = 'False'
            break
    return active


def last_interaction(case):
    last_inter = None
    for action in case['actions']:
        if action['xform_xmlns'] in LAST_INTERACTION_LIST:
            last_inter = action
    return last_inter['date']


def get_property(case, property):
    try:
        category = case[property]
    except AttributeError:
        category = ''
    return category


class RandomizationDate(fluff.Calculator):

    @fluff.date_emitter
    def date(self, case):
        yield {
            'date': get_randomization_date(case),
            'value': 1
        }


class UCLAPatientFluff(fluff.IndicatorDocument):

    document_class = CommCareCase
    domains = ('succeed',)
    document_filter = CustomFilter(lambda c: c.type == 'participant')

    group_by = ('domain', )
    save_direct_to_sql = True
    kafka_topic = topics.CASE

    name = flat_field(lambda case: case.full_name)
    mrn = flat_field(lambda case: case['mrn'])

    owner_id = flat_field(lambda case: case.owner_id)
    user_id = flat_field(lambda case: case.user_id)

    bp_category = flat_field(lambda case: get_property(case, 'BP_category'))
    care_site = flat_field(lambda case: get_property(case, 'care_site_display').lower())
    is_active = flat_field(lambda case: is_active(case))
    visit_name = flat_field(lambda case: visit_name(case))
    visit_days = flat_field(lambda case: visit_days(case))
    last_interaction = flat_field(lambda case: last_interaction(case))

    emitter = RandomizationDate()


UCLAPatientFluffPillow = UCLAPatientFluff.pillow()
