import logging
from django.conf import settings
import gevent
from casexml.apps.case.models import CommCareCase
from corehq.pillows import dynamic
from pact.enums import PACT_SCHEDULES_NAMESPACE
from pact.models import CDotWeeklySchedule
from pillowtop.listener import ElasticPillow, WAIT_HEARTBEAT


def schedule_mapping_generator():
    m = dynamic.DEFAULT_MAPPING_WRAPPER
    doc_class=CDotWeeklySchedule
    m['properties'] = dynamic.set_properties(doc_class)
    m['_meta']['created'] = "foo"
    return m
