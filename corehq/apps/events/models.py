import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from memoized import memoized

from casexml.apps.case.mock import (
    CaseBlock,
    CaseFactory,
    CaseIndex,
    CaseStructure,
)

from corehq.apps.es.case_search import CaseSearchES
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.models import CommCareUser, CouchUser
from corehq.apps.users.tasks import remove_indices_from_deleted_cases
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.models import CommCareCase, CommCareCaseIndex
from corehq.util.quickcache import quickcache

from .exceptions import InvalidAttendee
from .utils import (
    case_index_event_identifier,
    create_case_with_case_type,
    find_case_create_form,
    find_difference,
)

NOT_STARTED = 'Not started'
IN_PROGRESS = 'In progress'
UNDER_REVIEW = 'Under review'
REJECTED = 'Rejected'
ACCEPTED = 'Accepted'

ATTENDEE_LIST_STATUS_CHOICES = [
    (NOT_STARTED, _('Not started')),
    (IN_PROGRESS, _('In progress')),
    (UNDER_REVIEW, _('Under review')),
    (REJECTED, _('Rejected')),
    (ACCEPTED, _('Accepted')),
]

# Attendees are CommCareCase instances with this case type:
ATTENDEE_CASE_TYPE = 'commcare-attendee'

# An extension case with this case type links an attendee to an Event:
EVENT_ATTENDEE_CASE_TYPE = 'commcare-potential-attendee'

# Used internally as a host case for EVENT_ATTENDEE_CASE_TYPE
EVENT_CASE_TYPE = 'commcare-event'

# For attendees who are also mobile workers:
ATTENDEE_USER_ID_CASE_PROPERTY = 'commcare_user_id'


class EventObjectManager(models.Manager):

    def by_domain(self, domain, most_recent_first=False):
        if most_recent_first:
            return super(EventObjectManager, self).get_queryset().filter(domain=domain).order_by('start_date')
        return super(EventObjectManager, self).get_queryset().filter(domain=domain)

    def get_event(self, event_id):
        return super(EventObjectManager, self).get_queryset().get(event_id=event_id)


class Event(models.Model):
    """Attendance Tracking Event"""
    objects = EventObjectManager()

    name = models.CharField(max_length=100)
    domain = models.CharField(max_length=255)
    event_id = models.CharField(max_length=255, unique=True)
    start_date = models.DateField(null=False)
    end_date = models.DateField(null=False)
    attendance_target = models.IntegerField(null=False)
    total_attendance = models.IntegerField(null=False, default=0)
    sameday_reg = models.BooleanField(default=False)
    track_each_day = models.BooleanField(default=False)
    is_open = models.BooleanField(default=True)
    manager_id = models.CharField(max_length=255, null=False)
    attendee_list_status = models.CharField(
        max_length=255,
        null=False,
        choices=ATTENDEE_LIST_STATUS_CHOICES,
        default=NOT_STARTED,
    )

    class Meta:
        db_table = "commcare_event"
        indexes = (
            models.Index(fields=("event_id",)),
            models.Index(fields=("domain",)),
            models.Index(fields=("manager_id",)),
        )

    @quickcache(['self.event_id'])
    def get_expected_attendees(self):
        """
        Returns CommCareCase instances for the attendees for this Event.
        """
        # Attendee cases are associated with one or more Events using
        # extension cases. The extension cases have case type
        # EVENT_ATTENDEE_CASE_TYPE ('commcare-potential-attendee').
        #
        # The extension cases are owned by the Event's case-sharing
        # group so that all mobile workers in the group get the attendee
        # cases for the Event.
        event_attendee_cases = self._get_ext_cases()

        attendee_cases = []
        for case in event_attendee_cases:
            for index in case.indices:
                if index.referenced_type == ATTENDEE_CASE_TYPE:
                    attendee_cases.append(index.referenced_case)
        return attendee_cases

    def set_expected_attendees(self, attendee_cases):
        """
        Drops existing expected attendees, and creates extension cases
        linking ``attendee_cases`` to this Event.
        """
        self.get_expected_attendees.clear(self)

        self._close_ext_cases()

        ext_case_structs = []
        for attendee_case in attendee_cases:
            event_host = CaseStructure(case_id=self.event_id)
            attendee_host = CaseStructure(case_id=attendee_case.case_id)
            ext_case_structs.append(CaseStructure(
                indices=[
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
                        related_type=ATTENDEE_CASE_TYPE,
                    ),
                ],
                attrs={
                    'case_type': EVENT_ATTENDEE_CASE_TYPE,
                    'create': True,
                },
            ))
        self._case_factory.create_or_update_cases(ext_case_structs)

    def _get_ext_cases(self):
        """
        Returns 'commcare-potential-attendee' cases
        """
        ext_case_ids = CommCareCaseIndex.objects.get_extension_case_ids(
            self.domain,
            [self.event_id],
            include_closed=False,
        )
        return CommCareCase.objects.get_cases(ext_case_ids, self.domain)

    def _close_ext_cases(self):
        ext_case_ids = CommCareCaseIndex.objects.get_extension_case_ids(
            self.domain,
            [self.event_id],
            include_closed=False,
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
        # This is the only thing we use the Event case for. It does not
        # store any Event data other than its name.
        try:
            case = CommCareCase.objects.get_case(self.event_id, self.domain)
        except CaseNotFound:
            struct = CaseStructure(
                case_id=self.event_id,
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

    def save(self, expected_attendees=None):
        if not self.event_id:
            self.event_id = uuid.uuid4().hex
        event = super(Event, self).save()

        if expected_attendees is not None:
            self._update_attendees(expected_attendees)

        return event

    def delete(self, using=None, keep_parents=False):
        attendees_to_unassign = Attendee.objects.get_by_event_id(self.event_id, domain=self.domain)
        self._unassign_attendees(
            [attendee.case_id for attendee in attendees_to_unassign]
        )
        return super().delete(using, keep_parents)

    @property
    def status(self):
        return self.attendee_list_status

    @property
    def attendees(self):
        return Attendee.objects.get_by_event_id(self.event_id, self.domain)

    def _update_attendees(self, attendees_case_ids):
        current_attendees_ids = Attendee.objects.get_by_event_id(
            self.event_id,
            self.domain,
            only_ids=True
        )
        attendees_to_assign, attendees_to_unassign = find_difference(current_attendees_ids, attendees_case_ids)

        self._assign_attendees(list(attendees_to_assign))
        self._unassign_attendees(list(attendees_to_unassign))

    def _assign_attendees(self, attendees_case_ids):
        if not attendees_case_ids:
            return

        domain = self.domain
        event_id = self.event_id

        for parent_case_id in attendees_case_ids:
            case_args = {
                'domain': domain,
                'properties': {'event_id': event_id},
            }
            index_args = {
                'parent_case_id': parent_case_id,
                'identifier': case_index_event_identifier(event_id),
            }

            create_case_with_case_type(
                case_type=Attendee.EVENT_ATTENDEE_CASE_TYPE,
                case_args=case_args,
                index=index_args,
            )

    def _unassign_attendees(self, attendees_case_ids):
        if not attendees_case_ids:
            return

        extension_cases_ids = CommCareCaseIndex.objects.get_extension_case_ids(
            self.domain,
            attendees_case_ids
        )
        if not extension_cases_ids:
            return

        for extension_case in CommCareCase.objects.get_cases(extension_cases_ids):
            form = find_case_create_form(extension_case, self.domain)
            form.archive()

        remove_indices_from_deleted_cases(self.domain, extension_cases_ids)


class AttendeeCaseManager:
    """
    Offers an HQ-style Django-model-manager-like interface.
    """
    def by_domain(self, domain):
        """
        Returns a list of open attendee cases
        """
        case_ids = CommCareCase.objects.get_open_case_ids_in_domain_by_type(
            domain,
            ATTENDEE_CASE_TYPE,
        )
        return CommCareCase.objects.get_cases(case_ids, domain)


class AttendeeCase:
    """
    Allows code to interact with attendee CommCareCase instances as if
    they were Django models.
    """
    objects = AttendeeCaseManager()


def get_paginated_attendees(domain, limit, page, query=None):

    def attendee_as_user_dict(case: CommCareCase):
        # TODO: Don't use these properties
        user_id = case.get_case_property(ATTENDEE_USER_ID_CASE_PROPERTY)
        if user_id:
            user = CommCareUser.get_by_user_id(user_id, domain=domain)
            return {
                '_id': case.case_id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'base_username': user.username,
                'user_id': user_id,
                'username': user.raw_username,
            }
        else:
            try:
                first_name, last_name = case.name.split(' ', maxsplit=1)
            except ValueError:
                first_name, last_name = case.name, ''
            return {
                '_id': case.case_id,
                'first_name': first_name,
                'last_name': last_name,
                'base_username': '',
                'user_id': '',
                'username': '',
            }

    case_ids = CommCareCase.objects.get_open_case_ids_in_domain_by_type(
        domain,
        ATTENDEE_CASE_TYPE,
    )
    total = len(case_ids)
    if page:
        start, end = page_to_slice(limit, page)
        cases = CommCareCase.objects.get_cases(case_ids[start:end], domain)
    else:
        cases = CommCareCase.objects.get_cases(case_ids[:limit], domain)
    return [attendee_as_user_dict(c) for c in cases], total


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


class AttendeeObjectManager(models.Manager):

    def by_domain(self, domain):
        return super(AttendeeObjectManager, self).get_queryset().filter(domain=domain)

    def get_by_id(self, case_id, domain):
        return super(AttendeeObjectManager, self).get_queryset().get(domain=domain, case_id=case_id)

    def get_by_ids(self, case_ids, domain):
        return super(AttendeeObjectManager, self).get_queryset().filter(domain=domain, case_id__in=case_ids)

    def get_by_event_id(self, event_id, domain, only_ids=False):
        indices = CommCareCaseIndex.objects.get_by_identifier(
            domain=domain,
            identifier=case_index_event_identifier(event_id),
        )

        referenced_case_ids = [index.referenced_id for index in indices]
        if only_ids:
            return referenced_case_ids

        return self.get_by_ids(referenced_case_ids, domain)

    def by_user_id(self, user_id, domain):
        es_query = CaseSearchES().domain(domain).case_property_query(
            ATTENDEE_USER_ID_CASE_PROPERTY,
            user_id,
        )
        result = es_query.run().hits
        if not result:
            return None

        return self.get_by_id(case_id=result[0]['_id'], domain=domain)


class Attendee(models.Model):

    ATTENDEE_CASE_TYPE = 'commcare-attendee'
    EVENT_ATTENDEE_CASE_TYPE = 'commcare-potential-attendee'

    domain = models.CharField(max_length=255)
    case_id = models.CharField(max_length=126)
    objects = AttendeeObjectManager()

    class Meta:
        db_table = "commcare_attendee"
        indexes = (models.Index(fields=("domain",)),)

    def save(self, user_id):
        if not user_id:
            raise InvalidAttendee('Attendee must have user_id specified')

        if not self.domain:
            raise InvalidAttendee('Attendee must have domain specified')

        if not self.case_id:
            existing_attendee = Attendee.objects.by_user_id(user_id, self.domain)

            # This needs to be tested still
            if not existing_attendee:
                case_ = create_case_with_case_type(
                    case_type=Attendee.ATTENDEE_CASE_TYPE,
                    case_args={
                        'domain': self.domain,
                        'name': CouchUser.get_by_user_id(user_id).username,
                        'properties': {
                            ATTENDEE_USER_ID_CASE_PROPERTY: user_id,
                        }
                    },
                )
                self.case_id = case_.case_id

        return super(Attendee, self).save()

    def delete(self):
        form = find_case_create_form(
            CommCareCase.objects.get_case(self.case_id, self.domain),
            self.domain,
        )
        form.archive()
        return super(Attendee, self).delete()
