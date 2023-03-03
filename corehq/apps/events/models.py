import uuid

from django.utils.translation import gettext_lazy as _
from django.db import models


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
