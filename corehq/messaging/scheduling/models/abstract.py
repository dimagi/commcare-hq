from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.messaging.scheduling.dbaccessors import save_schedule_instance
from corehq.util.mixin import UUIDGeneratorMixin
from corehq.util.timezones.utils import get_timezone_for_domain, coerce_timezone_value
from datetime import datetime, tzinfo
from dimagi.utils.decorators.memoized import memoized
from django.db import models
from django.core.exceptions import ValidationError


class ScheduleForeignKeyMixin(models.Model):
    timed_schedule_id = models.IntegerField(null=True)

    class Meta:
        abstract = True

    class NoAvailableSchedule(Exception):
        pass

    class UnknownScheduleType(Exception):
        pass

    @property
    def schedule(self):
        from corehq.messaging.scheduling.models import TimedSchedule

        if self.timed_schedule_id:
            return TimedSchedule.objects.get(pk=self.timed_schedule_id)

        raise self.NoAvailableSchedule()

    @property
    @memoized
    def memoized_schedule(self):
        """
        This is named with a memoized_ prefix to be clear that it should only be used
        when the schedule is not changing.
        """
        return self.schedule

    @schedule.setter
    def schedule(self, value):
        from corehq.messaging.scheduling.models import TimedSchedule

        self.timed_schedule_id = None

        if isinstance(value, TimedSchedule):
            self.timed_schedule_id = value.pk
        else:
            raise self.UnknownScheduleType()


class ScheduleInstance(UUIDGeneratorMixin, ScheduleForeignKeyMixin):
    UUIDS_TO_GENERATE = ['schedule_instance_id']
    CONVERT_UUID_TO_HEX = False

    domain = models.CharField(max_length=126)
    schedule_instance_id = models.UUIDField()
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
    def create_for_recipient(cls, schedule, recipient_type, recipient_id, start_date=None,
            move_to_next_event_not_in_the_past=True):

        obj = cls(
            domain=schedule.domain,
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            current_event_num=0,
            schedule_iteration_num=1,
            active=True
        )

        obj.schedule = schedule
        schedule.set_first_event_due_timestamp(obj, start_date)

        if move_to_next_event_not_in_the_past:
            schedule.move_to_next_event_not_in_the_past(obj)

        save_schedule_instance(obj)
        return obj

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
            if self.memoized_schedule.include_descendant_locations:
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
        content = self.memoized_schedule.get_current_event_content(self)
        for recipient in self.expand_recipients():
            content.send(recipient)
        # As a precaution, always explicitly move to the next event after processing the current
        # event to prevent ever getting stuck on the current event.
        self.memoized_schedule.move_to_next_event(self)
        self.memoized_schedule.move_to_next_event_not_in_the_past(self)
        save_schedule_instance(self)


class Schedule(models.Model):
    domain = models.CharField(max_length=126)

    # Only matters when the recipient of a ScheduleInstance is a Location
    # If False, only include users at that location as recipients
    # If True, include all users at that location or at any descendant locations as recipients
    include_descendant_locations = models.BooleanField(default=False)

    class Meta:
        abstract = True

    def set_first_event_due_timestamp(self, instance, start_date=None):
        raise NotImplementedError()

    def move_to_next_event(self, instance):
        raise NotImplementedError()

    def get_current_event_content(self, instance):
        raise NotImplementedError()

    def move_to_next_event_not_in_the_past(self, instance):
        while instance.active and instance.next_event_due < datetime.utcnow():
            self.move_to_next_event(instance)


class ContentForeignKeyMixin(models.Model):
    sms_content = models.ForeignKey('scheduling.SMSContent', null=True, on_delete=models.CASCADE)
    email_content = models.ForeignKey('scheduling.EmailContent', null=True, on_delete=models.CASCADE)
    sms_survey_content = models.ForeignKey('scheduling.SMSSurveyContent', null=True, on_delete=models.CASCADE)
    ivr_survey_content = models.ForeignKey('scheduling.IVRSurveyContent', null=True, on_delete=models.CASCADE)

    class Meta:
        abstract = True

    class NoAvailableContent(Exception):
        pass

    class UnknownContentType(Exception):
        pass

    @property
    def content(self):
        if self.sms_content_id:
            return self.sms_content
        elif self.email_content_id:
            return self.email_content
        elif self.sms_survey_content_id:
            return self.sms_survey_content
        elif self.ivr_survey_content_id:
            return self.ivr_survey_content

        raise self.NoAvailableContent()

    @property
    @memoized
    def memoized_content(self):
        """
        This is named with a memoized_ prefix to be clear that it should only be used
        when the content is not changing.
        """
        return self.content

    @content.setter
    def content(self, value):
        from corehq.messaging.scheduling.models import (SMSContent, EmailContent,
            SMSSurveyContent, IVRSurveyContent)

        self.sms_content = None
        self.email_content = None
        self.sms_survey_content = None
        self.ivr_survey_content = None

        if isinstance(value, SMSContent):
            self.sms_content = value
        elif isinstance(value, EmailContent):
            self.email_content = value
        elif isinstance(value, SMSSurveyContent):
            self.sms_survey_content = value
        elif isinstance(value, IVRSurveyContent):
            self.ivr_survey_content = value
        else:
            raise self.UnknownContentType()


class Event(ContentForeignKeyMixin):
    order = models.IntegerField()

    class Meta:
        abstract = True


class Content(models.Model):
    class Meta:
        abstract = True

    def send(self, recipient):
        """
        :param recipient: a CommCareUser, WebUser, or CommCareCase/SQL
        representing the contact who should receive the content.
        """
        raise NotImplementedError()
