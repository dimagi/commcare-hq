from __future__ import annotations

import json
import uuid
from datetime import date, datetime

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.translation import gettext_lazy as _

from casexml.apps.case.const import CASE_INDEX_EXTENSION

from corehq.apps.groups.models import UnsavableGroup
from corehq.apps.hqcase.case_helper import CaseHelper
from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.models import CommCareCase, CommCareCaseIndex
from corehq.util.quickcache import quickcache

from .exceptions import AttendeeTrackedException

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

# Attendees can have locations the way mobile workers do
LOCATION_IDS_CASE_PROPERTY = 'commcare_location_ids'
PRIMARY_LOCATION_ID_CASE_PROPERTY = 'commcare_primary_location_id'


class AttendanceTrackingConfig(models.Model):
    domain = models.CharField(max_length=255, primary_key=True)

    # Automatically create attendees for mobile workers
    mobile_worker_attendees = models.BooleanField(default=False)

    # For projects with existing attendee cases
    attendee_case_type = models.CharField(
        max_length=255,
        default=DEFAULT_ATTENDEE_CASE_TYPE,
    )

    def save(self, *args, **kwargs):
        get_attendee_case_type.clear(self.domain)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        get_attendee_case_type.clear(self.domain)
        return super().delete(*args, **kwargs)


def toggle_mobile_worker_attendees(domain, attendees_enabled):
    AttendanceTrackingConfig.objects.update_or_create(
        domain=domain,
        defaults={'mobile_worker_attendees': attendees_enabled},
    )


def mobile_worker_attendees_enabled(domain):
    config = AttendanceTrackingConfig.objects.filter(domain=domain).first()
    return config.mobile_worker_attendees if config else False


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

    def by_domain(self, domain, not_started_first=False):
        if not_started_first:
            return super().get_queryset().filter(domain=domain).order_by('-start_date')
        return super().get_queryset().filter(domain=domain)


class Event(models.Model):
    """Attendance Tracking Event"""
    objects = EventObjectManager()

    name = models.CharField(max_length=100)
    domain = models.CharField(max_length=255)
    event_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    _case_id = models.UUIDField(null=True, default=None)
    start_date = models.DateField(null=False)
    end_date = models.DateField(null=True)
    location = models.ForeignKey(
        SQLLocation,
        to_field='location_id',
        on_delete=models.SET_NULL,
        null=True,
        default=None,
    )
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
        if self._case_id is None:
            self._create_case()
        return str(self._case_id)

    @property
    def group_id(self):
        return str(self.event_id)

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
        for case in self._get_extension_cases(case_type):
            for index in case.indices:
                if index.referenced_type == attendee_case_type:
                    attendee_cases.append(index.referenced_case)
        return attendee_cases

    def set_expected_attendees(self, attendee_cases):
        """
        Drops existing expected attendees, and creates
        ``EVENT_ATTENDEE_CASE_TYPE`` extension cases linking
        ``attendee_cases`` to this Event.

        ``attendee_cases`` is a list of CommCareCase instances or case
        IDs.
        """
        self.get_expected_attendees.clear(self)
        self._close_extension_cases(case_type=EVENT_ATTENDEE_CASE_TYPE)

        for case_id in iter_case_ids(attendee_cases):
            case_data = self._get_extension_case_data(
                case_type=EVENT_ATTENDEE_CASE_TYPE,
                attendee_case_id=case_id,
            )
            helper = CaseHelper(domain=self.domain)
            helper.create_case(case_data)

    def mark_attendance(self, attendee_cases, attended_datetime):
        """
        Creates ``ATTENDEE_DATE_CASE_TYPE`` extension cases linking
        ``attendee_cases`` to this Event at ``attended_datetime``.

        ``attendee_cases`` is a list of CommCareCase instances or case
        IDs. ``attended_datetime`` is a datetime instance or a string.
        """
        self.get_attended_attendees.clear(self)

        if isinstance(attended_datetime, datetime):
            attended_datetime = attended_datetime.isoformat(' ', 'seconds')

        for case_id in iter_case_ids(attendee_cases):
            case_data = self._get_extension_case_data(
                case_type=ATTENDEE_DATE_CASE_TYPE,
                attendee_case_id=case_id,
                case_properties={
                    ATTENDED_DATE_CASE_PROPERTY: attended_datetime,
                },
            )
            helper = CaseHelper(domain=self.domain)
            helper.create_case(case_data)

    def _get_extension_case_data(
        self,
        case_type,
        attendee_case_id,
        case_properties=None,
    ):
        return {
            'case_name': f"Event '{self.name}' | Attendee '{attendee_case_id}'",
            'case_type': case_type,
            'owner_id': self.group_id,
            'properties': case_properties or {},
            'indices': {
                'event-host': {
                    'case_type': EVENT_CASE_TYPE,
                    'case_id': self.case_id,
                    'relationship': CASE_INDEX_EXTENSION,
                },
                'attendee-host': {
                    'case_type': get_attendee_case_type(self.domain),
                    'case_id': attendee_case_id,
                    'relationship': CASE_INDEX_EXTENSION,
                }
            }
        }

    def _get_extension_cases(self, case_type=None):
        ext_case_ids = CommCareCaseIndex.objects.get_extension_case_ids(
            self.domain,
            [self.case_id],
            include_closed=False,
            case_type=case_type,
        )
        return CommCareCase.objects.get_cases(ext_case_ids, self.domain)

    def _close_extension_cases(self, case_type=None):
        ext_case_ids = CommCareCaseIndex.objects.get_extension_case_ids(
            self.domain,
            [self.case_id],
            include_closed=False,
            case_type=case_type,
        )
        for case_id in ext_case_ids:
            helper = CaseHelper(case_id=case_id, domain=self.domain)
            helper.close()

    @property
    def case(self):
        # In order to get 'commcare-potential-attendee' extension cases
        # efficiently, we use CommCareCaseIndexManager.get_reverse_indices()
        # ... and for that to work, the Event has a host case.
        #
        # This is the only thing we use the Event's case for. It does not
        # store any Event data other than its name, and is not used for anything
        # other than looking up extension cases.
        return CommCareCase.objects.get_case(self.case_id, self.domain)

    def _create_case(self):
        assert self._case_id is None, 'Case already exists'

        helper = CaseHelper(domain=self.domain)
        helper.create_case({
            'case_type': EVENT_CASE_TYPE,
            'case_name': self.name,
            'owner_id': self.manager_id,
        })
        # `handle_case_update()` does not allow us to set `case_id`
        # when creating a case, so we set `self._case_id` after the
        # case is created.
        self._case_id = uuid.UUID(helper.case.case_id)
        if self._state.adding is False:
            # Save the instance if it already exists in the database
            # otherwise wait until it is saved normally.
            # https://docs.djangoproject.com/en/3.2/ref/models/instances/#django.db.models.Model._state
            self.save()
        return helper.case

    def save(self, *args, **kwargs):
        if self._case_id is None:
            self._create_case()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._close_extension_cases()
        helper = CaseHelper(case_id=self.case_id, domain=self.domain)
        helper.close()
        return super().delete(*args, **kwargs)

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


class AttendeeModelManager(models.Manager):

    def get(self, *, case_id: str, domain: str) -> AttendeeModel:
        return AttendeeModel(case_id=case_id, domain=domain)

    def by_domain(
        self,
        domain: str,
        include_closed: bool = False,
    ) -> list[AttendeeModel]:
        if include_closed:
            get_case_ids = CommCareCase.objects.get_case_ids_in_domain
        else:
            get_case_ids = CommCareCase.objects.get_open_case_ids_in_domain_by_type
        case_type = get_attendee_case_type(domain)
        case_ids = get_case_ids(domain, case_type)
        return [
            AttendeeModel(case=case, domain=domain)
            for case in CommCareCase.objects.get_cases(case_ids, domain)
        ]

    def by_location_id(
        self,
        domain: str,
        location_id: str,
    ) -> list[AttendeeModel]:
        from .es import AttendeeSearchES

        location_ids = (
            SQLLocation.objects
            .get_locations_and_children_ids([location_id])
        )
        case_type = get_attendee_case_type(domain)
        es_query = (
            AttendeeSearchES()
            .domain(domain)
            .case_type(case_type)
            .is_closed(False)
            .attendee_location_filter(location_ids)
        )
        case_ids = es_query.get_ids()
        return [
            AttendeeModel(case=case, domain=domain)
            for case in CommCareCase.objects.get_cases(case_ids, domain)
        ]


class AttendeeModel(models.Model):
    """
    This class is for managing attendee cases using a ModelForm.

    Normal cases manage locations as supply points. Attendee cases
    manage locations the way ``CommCareUser`` does:

    * An attendee can have multiple locations, one of which is their
      primary location.

    * ``AttendeeCase`` locations are stored in special case properties
      the same way that ``CommCareUser`` locations are stored in special
      user metadata.

    """
    case_id = models.UUIDField(primary_key=True)
    domain = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    locations = models.TextField(blank=True, default='')
    primary_location = models.TextField(null=True, blank=True, default=None)
    user_id = models.TextField(max_length=36, blank=True, null=True)

    objects = AttendeeModelManager()

    class Meta:
        managed = False  # Allows us to use a ModelForm to edit attendees

    def __init__(self, *args, domain, case=None, case_id=None, **kwargs):
        assert case or case_id, '`case` or `case_id` is required'
        if case:
            case_id = case.case_id
        elif case_id:
            case = CommCareCase.objects.get_case(case_id, domain)
        self.case = case

        kwargs.setdefault('name', case.name)
        # `locations` is a TextField (or a CharField) because the form widget
        # renders it correctly. Django is OK with us assigning a list to it:
        loc_ids_str = case.get_case_property(LOCATION_IDS_CASE_PROPERTY) or ''
        kwargs.setdefault('locations', loc_ids_str.split())
        kwargs.setdefault(
            'primary_location',
            case.get_case_property(PRIMARY_LOCATION_ID_CASE_PROPERTY)
        )
        kwargs.setdefault(
            'user_id',
            case.get_case_property(ATTENDEE_USER_ID_CASE_PROPERTY)
        )
        super().__init__(*args, case_id=case_id, domain=domain, **kwargs)

    def save(self, *args, **kwargs):
        if isinstance(self.locations, str):
            self.locations = _parse_id_list_str(self.locations)
        helper = CaseHelper(case_id=self.case_id, domain=self.domain)
        case_data = {
            'case_name': self.name,
            'properties': {
                LOCATION_IDS_CASE_PROPERTY: ' '.join(self.locations),
                PRIMARY_LOCATION_ID_CASE_PROPERTY: self.primary_location or '',
                ATTENDEE_USER_ID_CASE_PROPERTY: self.user_id or '',
            },
        }
        helper.update(case_data)

    def delete(self, *args, **kwargs):
        if self.has_attended_events():
            raise AttendeeTrackedException

        helper = CaseHelper(case_id=self.case_id, domain=self.domain)
        helper.close()

    def has_attended_events(self):
        """
        Returns whether this attendee has been tracked in any events.
        These are events where the attendee has been marked as having attended.
        """
        ext_case_ids = CommCareCaseIndex.objects.get_extension_case_ids(
            self.domain,
            [self.case_id],
            include_closed=False,
            case_type=ATTENDEE_DATE_CASE_TYPE
        )
        return any(ext_case_ids)


def _parse_id_list_str(locations_str):
    """
    Given a string representation of a list of IDs, returns a list.

    >>> _parse_id_list_str("['abc123', 'def456']")
    ['abc123', 'def456']
    >>> _parse_id_list_str("['abc123', 'This isn\'t an ID!']")
    Traceback (most recent call last):
      ...
    json.decoder.JSONDecodeError: ...

    """
    # Using ast.literal_eval() is an alternative to the approach taken
    # here, but it is not safe for user-submitted data.
    # https://docs.python.org/3/library/ast.html#ast.literal_eval
    locations_json = locations_str.replace("'", '"')  # '["abc123", "def456"]'
    return json.loads(locations_json)


def iter_case_ids(cases_or_case_ids):
    for c in cases_or_case_ids:
        yield c if isinstance(c, str) else c.case_id
