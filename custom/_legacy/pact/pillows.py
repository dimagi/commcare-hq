from corehq.pillows import dynamic
from pact.models import CDotWeeklySchedule


def schedule_mapping_generator():
    m = dynamic.DEFAULT_MAPPING_WRAPPER
    doc_class=CDotWeeklySchedule
    m['properties'] = dynamic.set_properties(doc_class)
    m['_meta']['created'] = "foo"
    return m
