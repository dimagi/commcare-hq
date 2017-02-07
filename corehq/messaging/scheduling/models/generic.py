import jsonfield
import uuid
from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.messaging.scheduling.dbaccessors import (
    get_schedule_instances_for_schedule_and_recipient,
    save_schedule_instance,
)
from corehq.util.mixin import UUIDGeneratorMixin
from corehq.util.timezones.conversions import ServerTime, UserTime
from corehq.util.timezones.utils import get_timezone_for_domain, coerce_timezone_value
from datetime import timedelta, datetime, date, time, tzinfo
from dimagi.utils.decorators.memoized import memoized
from django.db import models
from django.core.exceptions import ValidationError


class ScheduleInstance(UUIDGeneratorMixin, models.Model):
    UUIDS_TO_GENERATE = ['schedule_instance_id']
    CONVERT_UUID_TO_HEX = False

    domain = models.CharField(max_length=126)
    schedule_instance_id = models.UUIDField()
    schedule_id = models.IntegerField()
    recipient_type = models.CharField(max_length=126)
    recipient_id = models.CharField(max_length=126)
    start_date = models.DateField()
    current_event_num = models.IntegerField()
    schedule_iteration_num = models.IntegerField()
    next_event_due = models.DateTimeField()
    active = models.BooleanField()

    class UnknownRecipient(Exception):
        pass

    @property
    @memoized
    def schedule(self):
        return Schedule.objects.get(pk=self.schedule_id)

    @property
    @memoized
    def schedule_events(self):
        return list(self.schedule.ordered_events)

    @property
    @memoized
    def recipient(self):
        if self.recipient_type == 'CommCareCase':
            return CaseAccessors(self.domain).get_case(self.recipient_id)
        elif self.recipient_type == 'CommCareUser':
            return CommCareUser.get(self.recipient_id)
        elif self.recipient_type == 'WebUser':
            return WebUser.get(self.recipient_id)
        elif self.recipient_type == 'CommCareCaseGroup':
            return CommCareCaseGroup.get(self.recipient_id)
        elif self.recipient_type == 'Group':
            return Group.get(self.recipient_id)
        elif self.recipient_type == 'Location':
            return SQLLocation.by_location_id(self.recipient_id)
        else:
            raise self.UnknownRecipient(self.recipient_type)

    @property
    @memoized
    def timezone(self):
        timezone = None

        if self.recipient_type in ('CommCareCase', 'CommCareUser', 'WebUser'):
            try:
                timezone = self.recipient.get_time_zone()
            except ValidationError:
                pass

        if not timezone:
            timezone = get_timezone_for_domain(self.domain)

        if isinstance(timezone, tzinfo):
            return timezone

        if isinstance(timezone, basestring):
            try:
                return coerce_timezone_value(timezone)
            except ValidationError:
                pass

        return pytz.UTC

    @classmethod
    def get_or_create_for_recipient(cls, schedule, recipient_type, recipient_id, start_date=None):
        instances = get_schedule_instances_for_schedule_and_recipient(schedule.pk, recipient_type, recipient_id)

        if len(instances) > 1:
            raise cls.MultipleObjectsReturned()

        if len(instances) == 1:
            return instances[0]

        obj = cls(
            domain=schedule.domain,
            schedule_id=schedule.pk,
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            current_event_num=0,
            schedule_iteration_num=1,
            active=True
        )

        obj.set_first_event_due_timestamp(start_date)
        save_schedule_instance(obj)
        return obj

    def set_first_event_due_timestamp(self, start_date=None):
        """
        If start_date is None, we set it automatically ensuring that
        self.next_event_due does not get set in the past for the first
        event.
        """
        if start_date:
            self.start_date = start_date
        else:
            self.start_date = ServerTime(datetime.utcnow()).user_time(self.timezone).done().date()

        self.set_next_event_due_timestamp()

        if not start_date and self.next_event_due < datetime.utcnow():
            self.start_date += timedelta(days=1)
            self.next_event_due += timedelta(days=1)

    def set_next_event_due_timestamp(self):
        current_event = self.schedule_events[self.current_event_num]
        days_since_start_date = (
            ((self.schedule_iteration_num - 1) * self.schedule.schedule_length) + current_event.day
        )

        timestamp = datetime.combine(self.start_date + timedelta(days=days_since_start_date), current_event.time)
        self.next_event_due = (
            UserTime(timestamp, self.timezone)
            .server_time()
            .done()
            .replace(tzinfo=None)
        )

    def move_to_next_event(self):
        self.current_event_num += 1
        if self.current_event_num >= len(self.schedule_events):
            self.schedule_iteration_num += 1
            self.current_event_num = 0
        self.set_next_event_due_timestamp()

        if (
            self.schedule.total_iterations != Schedule.REPEAT_INDEFINITELY and
            self.schedule_iteration_num > self.schedule.total_iterations
        ):
            self.active = False

    def move_to_next_event_not_in_the_past(self):
        while self.active and self.next_event_due < datetime.utcnow():
            self.move_to_next_event()

    def expand_recipients(self):
        """
        Can be used as a generator to iterate over all individual contacts who
        are the recipients of this ScheduleInstance.
        """
        if self.recipient_type in ('CommCareCase', 'CommCareUser', 'WebUser'):
            yield self.recipient
        elif self.recipient_type == 'CommCareCaseGroup':
            case_group = self.recipient
            for case in case_group.get_cases():
                yield case
        elif self.recipient_type == 'Group':
            group = self.recipient
            for user in group.get_users(is_active=True, only_commcare=False):
                yield user
        elif self.recipient_type == 'Location':
            location = self.recipient
            if self.schedule.include_descendant_locations:
                location_ids = location.get_descendants(include_self=True).filter(is_archived=False).location_ids()
            else:
                location_ids = [location.location_id]

            user_ids = set()
            for location_id in location_ids:
                for user in get_all_users_by_location(self.domain, location_id):
                    if user.is_active and user.get_id not in user_ids:
                        user_ids.add(user.get_id)
                        yield user
        else:
            raise self.UnknownRecipient(self.recipient_type)

    def handle_current_event(self):
        current_event = self.schedule_events[self.current_event_num]
        content = current_event.get_content()
        for recipient in self.expand_recipients():
            content.handle(recipient)
        # As a precaution, always explicitly move to the next event after processing the current
        # event to prevent ever getting stuck on the current event.
        self.move_to_next_event()
        self.move_to_next_event_not_in_the_past()
        save_schedule_instance(self)


class Schedule(models.Model):
    REPEAT_INDEFINITELY = -1

    domain = models.CharField(max_length=126)
    schedule_length = models.IntegerField()
    total_iterations = models.IntegerField()

    # Only matters when the recipient of a ScheduleInstance is a Location
    # If False, only include users at that location as recipients
    # If True, include all users at that location or at any descendant locations as recipients
    include_descendant_locations = models.BooleanField(default=False)

    @property
    def ordered_events(self):
        return self.event_set.order_by('order')

    @classmethod
    def create_daily_schedule(cls, domain, schedule_length=1, total_iterations=REPEAT_INDEFINITELY):
        return cls.objects.create(
            domain=domain,
            schedule_length=schedule_length,
            total_iterations=total_iterations
        )

    def add_event(self, day=0, time=None):
        return self.event_set.create(
            order=self.ordered_events.count(),
            day=day,
            time=time
        )


class Event(models.Model):
    schedule = models.ForeignKey('Schedule', on_delete=models.CASCADE)
    order = models.IntegerField()
    day = models.IntegerField()
    time = models.TimeField()

    class ContentObjectNotFound(Exception):
        pass

    class MultipleContentObjectsFound(Exception):
        pass

    def get_content(self):
        objs = list(self.content_set.all())

        if len(objs) > 1:
            raise MultipleContentObjectsFound(self.pk)

        if len(objs) == 0:
            raise ContentObjectNotFound(self.pk)

        return objs[0]

    def set_sms_content(self, message):
        self.content_set.all().delete()
        self.content_set.create(
            content_type=Content.CONTENT_SMS,
            message=message
        )
        return self


class Content(models.Model):
    CONTENT_SMS = 'SMS'

    event = models.ForeignKey('Event', on_delete=models.CASCADE)
    content_type = models.CharField(max_length=126)
    message = jsonfield.JSONField(default=dict, null=True)

    class UnknownContentType(Exception):
        pass

    def handle(self, recipient):
        """
        :param recipient: a CommCareUser, WebUser, or CommCareCase/SQL
        representing the contact who should receive the content.
        """
        method = {
            self.CONTENT_SMS: self.handle_sms,
        }.get(self.content_type)

        if not method:
            raise UnknownContentType(self.content_type)

        method(recipient)

    def handle_sms(self, recipient):
        print '*******************************'
        print 'To:', recipient
        print 'Message: ', self.message
        print '*******************************'
