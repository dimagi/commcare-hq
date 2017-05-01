import uuid
from dimagi.utils.decorators.memoized import memoized
from django.db import models
from corehq.messaging.scheduling.exceptions import (
    NoAvailableContent,
    UnknownContentType,
)
from corehq.messaging.scheduling import util


class Schedule(models.Model):
    schedule_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    domain = models.CharField(max_length=126, db_index=True)
    active = models.BooleanField(default=True)

    # Only matters when the recipient of a ScheduleInstance is a Location
    # If False, only include users at that location as recipients
    # If True, include all users at that location or at any descendant locations as recipients
    include_descendant_locations = models.BooleanField(default=False)

    # If None, the list of languages defined in the project for messaging will be
    # inspected and the default language there will be used.
    default_language_code = models.CharField(max_length=126, null=True)

    class Meta:
        abstract = True

    def set_first_event_due_timestamp(self, instance, start_date=None):
        raise NotImplementedError()

    def move_to_next_event(self, instance):
        raise NotImplementedError()

    def get_current_event_content(self, instance):
        raise NotImplementedError()

    def move_to_next_event_not_in_the_past(self, instance):
        while instance.active and instance.next_event_due < util.utcnow():
            self.move_to_next_event(instance)


class ContentForeignKeyMixin(models.Model):
    sms_content = models.ForeignKey('scheduling.SMSContent', null=True, on_delete=models.CASCADE)
    email_content = models.ForeignKey('scheduling.EmailContent', null=True, on_delete=models.CASCADE)
    sms_survey_content = models.ForeignKey('scheduling.SMSSurveyContent', null=True, on_delete=models.CASCADE)
    ivr_survey_content = models.ForeignKey('scheduling.IVRSurveyContent', null=True, on_delete=models.CASCADE)

    class Meta:
        abstract = True

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

        raise NoAvailableContent()

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
            raise UnknownContentType()


class Event(ContentForeignKeyMixin):
    # Order is only used for sorting the events in a schedule. Convention
    # dictates that it should start with 1 and be sequential, but technically
    # it doesn't matter as long as it sorts the events properly.
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


class Broadcast(models.Model):
    domain = models.CharField(max_length=126, db_index=True)
    name = models.CharField(max_length=1000)
    last_sent_timestamp = models.DateTimeField(null=True)

    class Meta:
        abstract = True
