from __future__ import annotations
from datetime import date
from typing import Literal
from django.utils.translation import gettext_lazy as _

from corehq.form_processor.models import CommCareCase
from corehq.apps.users.models import WebUser
from corehq.apps.events.utils import create_case_with_case_type
from corehq.sql_db.util import get_db_aliases_for_partitioned_query


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

EVENT_CASE_PROPERTIES = [
    'start_date',
    'end_date',
    'attendance_target',
    'sameday_reg',
    'track_each_day',
    'is_open',
    'attendee_list_status',
]


class Event:
    """Attendance Tracking Event"""
    domain: str
    name: str
    start_date: date
    end_date: date
    attendance_target: int
    sameday_reg: bool
    track_each_day: bool
    case: CommCareCase
    manager: WebUser
    is_open: bool = True

    attendee_list_status: AttendeeListStatus = 'Not started'

    # Todo: implement the following
    # attendance_takers: set[CommCareUser]
    # possible_attendees: set[Attendee]

    @classmethod
    def get_obj_from_data(cls, data) -> Event:
        event_obj = cls()

        event_obj.domain = data['domain']
        event_obj.name = data['name']
        event_obj.start_date = data['start_date']
        event_obj.end_date = data['end_date']
        event_obj.attendance_target = data['attendance_target']
        event_obj.sameday_reg = data['sameday_reg']
        event_obj.track_each_day = data['track_each_day']
        event_obj.manager = data['manager']
        event_obj.is_open = Event.is_open
        event_obj.attendee_list_status = Event.attendee_list_status

        if 'case' in data:
            event_obj.case = data['case']

        # Todo: implement the following
        # event_obj.attendance_takers = []
        # event_obj.possible_attendees = []

        return event_obj

    @classmethod
    def get_obj_from_case(cls, case: CommCareCase) -> Event:
        data = {
            'domain': case.domain,
            'name': case.name,
            'manager': WebUser.get_by_user_id(case.owner_id),
            'case': case,
            **{key: case.get_case_property(key) for key in EVENT_CASE_PROPERTIES}
        }
        return cls.get_obj_from_data(data)

    @property
    def status(self):
        return next(
            (value for key, value in ATTENDEE_LIST_STATUS_CHOICES if key == self.attendee_list_status)
        )

    @property
    def total_attendance(self):
        return self.case.get_case_property('total_attendance')

    def save(self):
        if hasattr(self, 'case'):
            # Todo: do an update on the existing case
            pass
        else:
            case = self._create_case()
            self.case = case

    def _create_case(self):
        # The Event class attributes map 1:1 with the case properties through EVENT_CASE_PROPERTIES
        case_json = {
            key: self.__dict__[key] for key in EVENT_CASE_PROPERTIES
        }
        case_args = {
            'domain': self.domain,
            'name': self.name,
            'owner_id': self.manager.user_id,
            'properties': case_json,
        }
        return create_case_with_case_type(EVENT_CASE_TYPE, case_args)


def get_domain_events(domain):
    events = []

    for db in get_db_aliases_for_partitioned_query():
        for case_ in CommCareCase.objects.using(db).filter(domain=domain, type=EVENT_CASE_TYPE):
            event = Event.get_obj_from_case(case_)
            events.append(event)

    return events
