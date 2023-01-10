from __future__ import annotations

from datetime import date, timedelta
from typing import Literal, Union

from django.utils.translation import gettext_lazy as _

from corehq.apps.users.models import CommCareUser, WebUser
from corehq.form_processor.models import CommCareCase

DateOrRange = Union[date, tuple[date, date]]

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

EVENT_CASE_TYPE = 'cchq-event'

ATTENDEE_CASE_TYPE = 'cchq-attendee'

ATTENDEE_USER_ID_CASE_PROPERTY = 'mobile_worker_id'


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
    attendance_takers: set[CommCareUser]

    possible_attendees: set[Attendee]

    is_open: bool = True
    attendee_list_status: AttendeeListStatus = 'Not started'

    @property
    def days(self) -> list[DateOrRange]:
        if self.track_each_day:
            num_days = (self.end - self.start).days + 1  # include self.end
            return [self.start + timedelta(days=x) for x in range(0, num_days)]
        return [(self.start, self.end)]

    def get_all_attendees(self) -> set[Attendee]:
        """
        Returns all attendees, including those who attended only some of
        the days.
        """
        ...

    def get_attendees_by_day(self) -> dict[DateOrRange, set[Attendee]]:
        """
        Returns a dictionary keyed by day, with the set of Attendees for
        that day. If ``self.track_each_day`` is ``False``, the
        dictionary will have the Event's date range as its only key.
        """
        ...

    def get_attendees_on_day(self, day: DateOrRange) -> set[Attendee]:
        ...

    def get_days_by_attendee(self) -> dict[Attendee, list[DateOrRange]]:
        """
        Returns a dictionary keyed by Attendee, with the list of days on
        which they attended. If ``self.track_each_day`` is ``False``,
        the list will contain a single date range.
        """
        ...


class EventDay:
    """
    Track attendees for a day of an Event, or date range if
    ``Event.track_each_day`` is ``False``.
    """
    domain: str
    event: Event
    day: DateOrRange
    attendees: set[Attendee]


class Attendee:
    """Attendee of an Event, possibly a mobile worker"""
    domain: str
    case: CommCareCase  # ATTENDEE_CASE_TYPE

    @property
    def full_name(self) -> str:
        if self.user:
            return self.user.full_name
        return self.case.name

    @property
    def user(self) -> CommCareUser | None:
        """
        Returns the user referenced by the case's ``mobile_worker_id``
        case property, or ``None`` if it is not set.
        """
        user_id = self.case.get_case_property(ATTENDEE_USER_ID_CASE_PROPERTY)
        if user_id:
            return CommCareUser.get_by_user_id(user_id, self.domain)
        return None

    def get_event_history(self) -> dict[Event, list[DateOrRange]]:
        """
        Returns a dictionary keyed by Event, with a list of days
        attended. If ``Event.track_each_day`` is ``False``, the list
        will contain the Event's date range.
        """
        ...


def collate_attendance_dates(domain: str, event: Event) -> None:
    ...
