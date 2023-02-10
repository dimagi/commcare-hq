from datetime import date
from typing import Literal

from corehq.form_processor.models import CommCareCase
from corehq.apps.es.case_search import CaseSearchES
from corehq.apps.users.models import WebUser
from corehq.apps.events.utils import wrap_es_case_as_event

from django.utils.translation import gettext_lazy as _

EVENT_CASE_TYPE = 'commcare-event'

AttendeeListStatus = Literal[
    'Not started',
    'In progress',
    'Under review',
    'Rejected',
    'Accepted',
]
ATTENDEE_LIST_STATUS_CHOICES = [
    ('Not started', _('Not started')),
    ('In progress', _('In progress')),
    ('Under review', _('Under review')),
    ('Rejected', _('Rejected')),
    ('Accepted', _('Accepted')),
]


class Event:
    """Attendance Tracking Event"""
    domain: str
    name: str
    start: date
    end: date
    attendance_target: int
    sameday_reg: bool
    track_each_day: bool  # If False, attendance applies to whole event

    case: CommCareCase  # EVENT_CASE_TYPE

    program_manager: WebUser
    is_open: bool = True
    attendee_list_status: AttendeeListStatus = 'Not started'

    @property
    def status(self):
        return next(
            (value for key, value in ATTENDEE_LIST_STATUS_CHOICES if key == self.attendee_list_status)
        )

    @property
    def total_attendance(self):
        return self.case.get_case_property('total_attendance')


def domain_events_from_es(domain) -> Event:
    return [
        wrap_es_case_as_event(result)
        for result in domain_events_es_query(domain).run().hits
    ]


def domain_events_es_query(domain) -> CaseSearchES:
    return CaseSearchES().domain(domain).case_type(EVENT_CASE_TYPE)
