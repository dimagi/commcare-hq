import uuid

from django.utils.translation import gettext_lazy as _
from django.db import models
from corehq.form_processor.models import CommCareCase, CommCareCaseIndex
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from corehq.apps.events.utils import case_index_event_identifier


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


class Event(models.Model):
    """Attendance Tracking Event"""
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

    @classmethod
    def by_domain(cls, domain, most_recent_first=False):
        if most_recent_first:
            return cls.objects.filter(domain=domain).order_by('start_date')
        return cls.objects.filter(domain=domain)

    def save(self):
        if not self.event_id:
            self.event_id = uuid.uuid4().hex
        super(Event, self).save()

    @property
    def status(self):
        return self.attendee_list_status

    def _update_attendees(self, attendees_case_ids):
        current_attendees_ids = Attendee.get_by_event_id(
            self.event_id,
            self.domain,
            only_ids=True
        )

        attendees_to_assign, attendees_to_unassign = find_difference(
            current_attendees_ids,
            attendees_case_ids
        )

        self._assign_attendees(attendees_to_assign)
        self._unassign_attendees(attendees_to_unassign)

        self.expected_attendees = Attendee.get_by_event_id(self.event_id, self.domain)

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
        # Todo: maybe refactor to use 'tag_cases_as_deleted_and_remove_indices'

        if not attendees_case_ids:
            return

        extension_case_ids = CommCareCaseIndex.objects.get_extension_case_ids(
            domain=self.domain,
            case_ids=list(attendees_case_ids),
        )

        CommCareCase.objects.soft_delete_cases(
            domain=self.domain,
            case_ids=extension_case_ids,
        )

        for db in get_db_aliases_for_partitioned_query():
            CommCareCaseIndex.objects.using(db)\
                .filter(referenced_id__in=attendees_case_ids)\
                .delete()


def get_domain_attendee_cases(domain):
    return []


class Attendee:
    domain: str
    case: CommCareCase

    ATTENDEE_CASE_TYPE = 'commcare-attendee'
    EVENT_ATTENDEE_CASE_TYPE = 'commcare-potential-attendee'

    def __init__(self, *args, **kwargs):
        self.domain = kwargs['domain']
        self.case = kwargs['case']

    @classmethod
    def get_domain_cases(cls, domain):
        return [
            wrap_case_search_hit(case_)
            for case_ in CaseSearchES().domain(domain).case_type(cls.ATTENDEE_CASE_TYPE).run().hits
        ]

    @classmethod
    def get_by_ids(cls, case_ids, domain) -> set[Attendee]:
        return [
            cls(domain=domain, case=case_)
            for case_ in CommCareCase.objects.get_cases(case_ids, domain)
        ]

    @classmethod
    def get_by_event_id(cls, event_id, domain, only_ids=False) -> set[Attendee]:
        indices = CommCareCaseIndex.objects.get_by_identifier(
            domain=domain,
            identifier=case_index_event_identifier(event_id),
        )

        referenced_case_ids = [index.referenced_id for index in indices]
        if only_ids:
            return referenced_case_ids

        return cls.get_by_ids(referenced_case_ids, domain)
