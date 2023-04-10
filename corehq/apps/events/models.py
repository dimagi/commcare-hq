import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from memoized import memoized

from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure
from corehq.apps.es import CaseES

from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.models import CommCareCase, CommCareCaseIndex
from corehq.util.quickcache import quickcache
from django.contrib.postgres.fields import ArrayField
from corehq.apps.groups.models import UnsavableGroup
from datetime import datetime
from datetime import date


# Attendee list status is set by the Attendance Coordinator after the
# event is over
ATTENDEE_LIST_UNDER_REVIEW = 'Under review'
ATTENDEE_LIST_REJECTED = 'Rejected'
ATTENDEE_LIST_ACCEPTED = 'Accepted'
ATTENDEE_LIST_STATUS_CHOICES = [
    (ATTENDEE_LIST_UNDER_REVIEW, _('Attendee list under review')),
    (ATTENDEE_LIST_REJECTED, _('Attendee list rejected')),
    (ATTENDEE_LIST_ACCEPTED, _('Attendee list accepted')),
]

# Event status is determined by the event's start and end dates
EVENT_NOT_STARTED = 'Not started'
EVENT_IN_PROGRESS = 'In progress'
EVENT_STATUS_TRANS = {
    EVENT_NOT_STARTED: _('Event not started'),
    EVENT_IN_PROGRESS: _('Event in progress'),
    ATTENDEE_LIST_UNDER_REVIEW: _('Attendee list under review'),
    ATTENDEE_LIST_REJECTED: _('Attendee list rejected'),
    ATTENDEE_LIST_ACCEPTED: _('Attendee list accepted'),
}

# DO NOT USE. Use `get_attendee_case_type()` instead.
#
# The default case type of attendees, unless the domain already has
# attendees.
DEFAULT_ATTENDEE_CASE_TYPE = 'commcare-attendee'


# An extension case with this case type links an attendee to an Event:
EVENT_ATTENDEE_CASE_TYPE = 'commcare-potential-attendee'

# An extension case that captures the attendace the attended date
#   will be stored on 'attendance_date' case property.
ATTENDEE_DATE_CASE_TYPE = 'commcare-attendance-date'

ATTENDED_DATE_CASE_PROPERTY = 'attendance_date'

"""
The case-structure:

commcare-event      commcare-attendee
   |                 |
   commcare-potential-attendee

commcare-event      commcare-attendee
   |                   |
   commcare-attendance-date
"""

# Used internally as a host case for EVENT_ATTENDEE_CASE_TYPE
EVENT_CASE_TYPE = 'commcare-event'

# For attendees who are also mobile workers:
ATTENDEE_USER_ID_CASE_PROPERTY = 'commcare_user_id'


class AttendanceTrackingConfig(models.Model):
    domain = models.CharField(max_length=255, primary_key=True)

    # Automatically create attendees for mobile workers
    mobile_worker_attendees = models.BooleanField(default=False)

    # For projects with existing attendee cases
    attendee_case_type = models.CharField(
        max_length=255,
        default=DEFAULT_ATTENDEE_CASE_TYPE,
    )

    @staticmethod
    def toggle_mobile_worker_attendees(domain, value):
        config, _created = AttendanceTrackingConfig.objects.get_or_create(domain=domain)
        config.mobile_worker_attendees = value
        config.save()

    @staticmethod
    def mobile_workers_can_be_attendees(domain):
        try:
            config = AttendanceTrackingConfig.objects.get(pk=domain)
            return config.mobile_worker_attendees
        except AttendanceTrackingConfig.DoesNotExist:
            return False


@quickcache(['domain'])
def get_attendee_case_type(domain):
    """
    Returns the case type for Attendee cases.

    AttendanceTrackingConfig will be configured for domains that already
    have attendee cases. Defaults to ``DEFAULT_ATTENDEE_CASE_TYPE``.
    """
    try:
        config = AttendanceTrackingConfig.objects.get(pk=domain)
    except AttendanceTrackingConfig.DoesNotExist:
        return DEFAULT_ATTENDEE_CASE_TYPE
    return config.attendee_case_type


class EventObjectManager(models.Manager):

    def by_domain(self, domain, most_recent_first=False):
        if most_recent_first:
            return super().get_queryset().filter(domain=domain).order_by('start_date')
        return super().get_queryset().filter(domain=domain)


class Event(models.Model):
    """Attendance Tracking Event"""
    objects = EventObjectManager()

    name = models.CharField(max_length=100)
    domain = models.CharField(max_length=255)
    event_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    _case_id = models.UUIDField(null=False, default=uuid.uuid4)
    start_date = models.DateField(null=False)
    end_date = models.DateField(null=True)
    attendance_target = models.IntegerField(null=False)
    total_attendance = models.IntegerField(null=False, default=0)
    sameday_reg = models.BooleanField(default=False)
    track_each_day = models.BooleanField(default=False)
    is_open = models.BooleanField(default=True)
    manager_id = models.CharField(max_length=255, null=False)
    _attendance_taker_ids = ArrayField(
        models.UUIDField(),
        blank=True,
        null=True,
        default=list
    )
    # attendee_list_status is only applicable after end_date has passed
    # and the Attendance Coordinator can review the list of attendees.
    # If end_date is null, attendee_list_status is not used.
    attendee_list_status = models.CharField(
        max_length=255,
        null=False,
        choices=ATTENDEE_LIST_STATUS_CHOICES,
        default=ATTENDEE_LIST_UNDER_REVIEW,
    )

    class Meta:
        db_table = "commcare_event"
        indexes = (
            models.Index(fields=("domain",)),
            models.Index(fields=("manager_id",)),
        )

    @property
    def case_id(self):
        try:
            return self._case_id.hex
        except AttributeError:
            return self._case_id

    @property
    def group_id(self):
        try:
            return self.event_id.hex
        except AttributeError:
            return self.event_id

    @property
    def attendance_taker_ids(self):
        return [uuid.hex for uuid in self._attendance_taker_ids]

    @attendance_taker_ids.setter
    def attendance_taker_ids(self, value):
        self._attendance_taker_ids = [uuid.UUID(hex=v) for v in value]

    def get_fake_case_sharing_group(self, user_id):
        """
        Returns a group object that cannot be saved.

        This is used for giving users access via case sharing groups,
        without having a real group for every event that we have to
        manage.
        """
        return UnsavableGroup(
            _id=self.group_id,
            domain=self.domain,
            users=[user_id],
            last_modified=datetime.utcnow(),
            name=self.name + ' Event',
            case_sharing=True,
            reporting=False,
            metadata={},
        )

    @quickcache(['self.event_id'])
    def get_expected_attendees(self):
        """
        Returns CommCareCase instances for the attendees for this Event.
        """
        return self._get_attendee_cases_related_to(
            EVENT_ATTENDEE_CASE_TYPE
        )

    @quickcache(['self.event_id'])
    def get_attended_attendees(self):
        return self._get_attendee_cases_related_to(
            ATTENDEE_DATE_CASE_TYPE
        )

    def _get_attendee_cases_related_to(self, case_type):
        # Attendee cases are associated with one or more Events using
        # extension cases. The extension cases have case types
        # EVENT_ATTENDEE_CASE_TYPE ('commcare-potential-attendee') or
        # ATTENDEE_DATE_CASE_TYPE ('commcare-attendance-date').
        #
        # The extension cases are owned by the Event's case-sharing
        # group so that all mobile workers in the group get the attendee
        # cases for the Event.

        # CommCareCaseIndex.objects.get_extension_case_ids only supports
        #   fetching by exclude_for_case_type, so fetch by exclusion
        attendee_case_type = get_attendee_case_type(self.domain)
        attendee_cases = []
        for case in self._get_ext_cases(case_type):
            for index in case.indices:
                if index.referenced_type == attendee_case_type:
                    attendee_cases.append(index.referenced_case)
        return attendee_cases

    def set_expected_attendees(self, attendee_cases):
        """
        Drops existing expected attendees, and creates extension cases
        linking ``attendee_cases`` to this Event.

        ``attendee_cases`` is a list of CommCareCase instances or case
        IDs.
        """
        self.get_expected_attendees.clear(self)
        self._close_ext_cases(case_type=EVENT_ATTENDEE_CASE_TYPE)

        case_structures = []
        for case_id in iter_case_ids(attendee_cases):
            event_host = CaseStructure(case_id=self.case_id)
            attendee_host = CaseStructure(case_id=case_id)
            case_structures.append(CaseStructure(
                indices=self._get_host_indices(event_host, attendee_host),
                attrs={
                    'case_type': EVENT_ATTENDEE_CASE_TYPE,
                    'owner_id': self.group_id,
                    'create': True,
                },
            ))
        self._case_factory.create_or_update_cases(case_structures)

    def mark_attendance(self, attendee_cases, attended_datetime):
        """
        Creates ``ATTENDEE_DATE_CASE_TYPE`` extension cases for this event
        and ``attendee_cases``. Also sets the ``ATTENDED_DATE_CASE_PROPERTY``
        property to ``attended_datetime``.
        """
        self.get_attended_attendees.clear(self)

        case_structures = []
        for case_id in iter_case_ids(attendee_cases):
            event_host = CaseStructure(case_id=self.case_id)
            attendee_host = CaseStructure(case_id=case_id)
            case_structures.append(CaseStructure(
                indices=self._get_host_indices(event_host, attendee_host),
                attrs={
                    'case_type': ATTENDEE_DATE_CASE_TYPE,
                    'owner_id': self.group_id,
                    'create': True,
                    'update': {
                        ATTENDED_DATE_CASE_PROPERTY: attended_datetime
                    }
                },
            ))
        self._case_factory.create_or_update_cases(case_structures)

    def _get_host_indices(self, event_host, attendee_host):
        return [
            CaseIndex(
                relationship='extension',
                identifier='event-host',
                related_structure=event_host,
                related_type=EVENT_CASE_TYPE,
            ),
            CaseIndex(
                relationship='extension',
                identifier='attendee-host',
                related_structure=attendee_host,
                related_type=get_attendee_case_type(self.domain),
            ),
        ]

    def _get_ext_cases(self, case_type=None):
        """
        Returns this Event's open extension cases.
        """
        ext_case_ids = CommCareCaseIndex.objects.get_extension_case_ids(
            self.domain,
            [self.case_id],
            include_closed=False,
            case_type=case_type,
        )
        return CommCareCase.objects.get_cases(ext_case_ids, self.domain)

    def _close_ext_cases(self, case_type=None):
        ext_case_ids = CommCareCaseIndex.objects.get_extension_case_ids(
            self.domain,
            [self.case_id],
            include_closed=False,
            case_type=case_type,
        )
        self._case_factory.create_or_update_cases([
            CaseStructure(case_id=case_id, attrs={'close': True})
            for case_id in ext_case_ids
        ])

    @property
    def case(self):
        # In order to get 'commcare-potential-attendee' extension cases
        # efficiently, we use CommCareCaseIndexManager.get_reverse_indices()
        # ... and for that to work, the Event has a host case.
        #
        # This is the only thing we use the Event's case for. It does not
        # store any Event data other than its name, and is not used for anything
        # other than looking up extension cases.
        try:
            case = CommCareCase.objects.get_case(self.case_id, self.domain)
        except CaseNotFound:
            struct = CaseStructure(
                case_id=self.case_id,
                attrs={
                    'owner_id': self.manager_id,
                    'case_type': EVENT_CASE_TYPE,
                    'case_name': self.name,
                    'create': True,
                },
            )
            (case,) = self._case_factory.create_or_update_cases([struct])
        return case

    @property
    @memoized
    def _case_factory(self):
        return CaseFactory(domain=self.domain)

    def delete(self, using=None, keep_parents=False):
        self._close_ext_cases()
        self._case_factory.close_case(self.case_id)
        return super().delete(using, keep_parents)

    @property
    def status(self):
        # Note: The return value is not translated. Use
        # EVENT_STATUS_TRANS for translations
        today = date.today()

        if today < self.start_date:
            return EVENT_NOT_STARTED
        elif self.start_date <= today <= self.end_date:
            return EVENT_IN_PROGRESS
        else:
            return self.attendee_list_status

    def get_total_attendance_takers(self):
        return len(self.attendance_taker_ids)


def get_user_case_sharing_groups_for_events(commcare_user):
    """
    Creates a case sharing group for every ``Event`` that the
    ``commcare_user`` is an attendance taker for in their domain.
    """
    for event in Event.objects.by_domain(commcare_user.domain):
        if commcare_user.user_id in event.attendance_taker_ids:
            yield event.get_fake_case_sharing_group(commcare_user.user_id)

class AttendeeCaseManager:
    def by_domain(
        self,
        domain: str,
        include_closed: bool = False,
    ) -> list[CommCareCase]:
        if include_closed:
            get_case_ids = CommCareCase.objects.get_case_ids_in_domain
        else:
            get_case_ids = CommCareCase.objects.get_open_case_ids_in_domain_by_type
        case_type = get_attendee_case_type(domain)
        case_ids = get_case_ids(domain, case_type)
        return CommCareCase.objects.get_cases(case_ids, domain)


class AttendeeCase:
    """
    Allows code to interact with attendee CommCareCase instances as if
    they were Django models.
    """
    objects = AttendeeCaseManager()


def get_paginated_attendees(domain, limit, page, query=None):
    case_type = get_attendee_case_type(domain)
    if query:
        es_query = (
            CaseES()
            .domain(domain)
            .case_type(case_type)
            .is_closed(False)
            .term('name', query)
        )
        total = es_query.count()
        case_ids = es_query.get_ids()
    else:
        case_ids = CommCareCase.objects.get_open_case_ids_in_domain_by_type(
            domain,
            case_type,
        )
        total = len(case_ids)
    if page:
        start, end = page_to_slice(limit, page)
        cases = CommCareCase.objects.get_cases(case_ids[start:end], domain)
    else:
        cases = CommCareCase.objects.get_cases(case_ids[:limit], domain)
    return cases, total


def page_to_slice(limit, page):
    """
    Converts ``limit``, ``page`` to start and end indices.

    Assumes page numbering starts at 1.

    >>> names = ['Harry', 'Hermione', 'Ron']
    >>> start, end = page_to_slice(limit=1, page=2)
    >>> names[start:end]
    ['Hermione']
    """
    assert page > 0, 'Page numbering starts at 1'

    start = (page - 1) * limit
    end = start + limit
    return start, end


def iter_case_ids(cases_or_case_ids):
    for c in cases_or_case_ids:
        yield c if isinstance(c, str) else c.case_id
