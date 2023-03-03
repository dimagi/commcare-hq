import uuid

from django.utils.translation import gettext_lazy as _
from django.db import models

from corehq.apps.users.tasks import remove_indices_from_deleted_cases
from corehq.form_processor.models import CommCareCase, CommCareCaseIndex, XFormInstance
from corehq.apps.users.models import CouchUser
from corehq.apps.events.utils import find_difference
from corehq.apps.events.exceptions import InvalidAttendee
from corehq.apps.hqcase.utils import submit_case_blocks
from casexml.apps.case.mock import CaseBlock


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


class EventObjectManager(models.Manager):

    def by_domain(self, domain, most_recent_first=False):
        if most_recent_first:
            return super(EventObjectManager, self).get_queryset().filter(domain=domain).order_by('start_date')
        return super(EventObjectManager, self).get_queryset().filter(domain=domain)


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

    def save(self, expected_attendees=None):
        if not self.event_id:
            self.event_id = uuid.uuid4().hex
        event = super(Event, self).save()

        if expected_attendees is not None:
            self._update_attendees(expected_attendees)

        return event

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

        attendees_to_assign, attendees_to_unassign = find_difference(
            current_attendees_ids,
            attendees_case_ids
        )

        self._assign_attendees(list(attendees_to_assign))
        self._unassign_attendees(list(attendees_to_unassign))

    def _assign_attendees(self, attendees_case_ids):
        if not attendees_case_ids:
            return

        # How to make this idempotent?
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
        """
        This method deletes the indices and cases linking the domain attendees to the event
        """
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


class AttendeeObjectManager(models.Manager):

    def by_domain(self, domain):
        return super(AttendeeObjectManager, self).get_queryset().filter(domain=domain)

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
            case_ = create_case_with_case_type(
                case_type=Attendee.ATTENDEE_CASE_TYPE,
                case_args={
                    'domain': self.domain,
                    'name': CouchUser.get_by_user_id(user_id).username,
                    'properties': {
                        'commcare_user_id': user_id,
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
        super(Attendee, self).delete()


def create_case_with_case_type(case_type, case_args, index=None):
    case_block = CaseBlock(
        case_id=uuid.uuid4().hex,
        case_type=case_type,
        case_name=case_args.get('name', None),
        domain=case_args['domain'],
        owner_id=case_args.get('owner_id', ''),
        update=case_args['properties'],
        create=True,
    )
    _, cases = submit_case_blocks(
        [case_block.as_text()],
        domain=case_args['domain'],
    )
    case_ = cases[0]

    if index is not None:
        case_.track_create(CommCareCaseIndex(
            case=case_,
            domain=case_.domain,
            referenced_id=index.get('parent_case_id'),
            relationship_id=CommCareCaseIndex.EXTENSION,
            referenced_type=case_.type,
            identifier=index.get('identifier', 'host'),
        ))
        case_.save(with_tracked_models=True)

    return case_


def case_index_event_identifier(event_id):
    return f'event-{event_id}'


def find_case_create_form(commcare_case, domain):
    form_id = next(
        (t.form_id for t in commcare_case.transactions if t.is_case_create)
    )
    return XFormInstance.objects.get_form(form_id, domain)
