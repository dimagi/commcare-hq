from __future__ import absolute_import
import jsonfield
import uuid
from dimagi.utils.decorators.memoized import memoized
from django.db import models, transaction
from corehq.apps.reminders.util import get_one_way_number_for_recipient
from corehq.apps.translations.models import StandaloneTranslationDoc
from corehq.apps.users.models import CommCareUser
from corehq.messaging.scheduling.exceptions import (
    NoAvailableContent,
    UnknownContentType,
)
from corehq.messaging.scheduling import util


class Schedule(models.Model):
    UI_TYPE_IMMEDIATE = 'I'
    UI_TYPE_DAILY = 'D'
    UI_TYPE_WEEKLY = 'W'
    UI_TYPE_MONTHLY = 'M'
    UI_TYPE_UNKNOWN = 'X'

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

    # If True, the framework looks for a backend named TEST to send messages for
    # this schedule.
    is_test = models.BooleanField(default=True)

    # This metadata will be passed to any messages generated from this schedule.
    custom_metadata = jsonfield.JSONField(null=True, default=None)

    # One of the UI_TYPE_* constants describing the type of UI that should be used
    # to edit this schedule.
    ui_type = models.CharField(max_length=1, default=UI_TYPE_UNKNOWN)

    class Meta:
        abstract = True

    def set_first_event_due_timestamp(self, instance, start_date=None):
        raise NotImplementedError()

    def move_to_next_event(self, instance):
        raise NotImplementedError()

    def get_current_event_content(self, instance):
        raise NotImplementedError()

    def total_iterations_complete(self, instance):
        """
        Should return True if the schedule instance has completed the total
        number of iterations for this schedule.
        """
        raise NotImplementedError()

    def move_to_next_event(self, instance):
        instance.current_event_num += 1
        if instance.current_event_num >= len(self.memoized_events):
            instance.schedule_iteration_num += 1
            instance.current_event_num = 0
        self.set_next_event_due_timestamp(instance)

        if self.total_iterations_complete(instance):
            instance.active = False

    def move_to_next_event_not_in_the_past(self, instance):
        while instance.active and instance.next_event_due < util.utcnow():
            self.move_to_next_event(instance)

    def set_extra_scheduling_options(self, options):
        if not options:
            return

        for k, v in options.items():
            setattr(self, k, v)

    @property
    @memoized
    def memoized_language_set(self):
        from corehq.messaging.scheduling.models import SMSContent, EmailContent

        result = set()
        for event in self.memoized_events:
            content = event.memoized_content
            if isinstance(content, SMSContent):
                result |= set(content.message)
            elif isinstance(content, EmailContent):
                result |= set(content.subject)
                result |= set(content.message)

        return result

    def delete_related_events(self):
        """
        Deletes all Event and Content objects related to this Schedule.
        """
        raise NotImplementedError()

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            self.delete_related_events()
            super(Schedule, self).delete(*args, **kwargs)


class ContentForeignKeyMixin(models.Model):
    sms_content = models.ForeignKey('scheduling.SMSContent', null=True, on_delete=models.CASCADE)
    email_content = models.ForeignKey('scheduling.EmailContent', null=True, on_delete=models.CASCADE)
    sms_survey_content = models.ForeignKey('scheduling.SMSSurveyContent', null=True, on_delete=models.CASCADE)
    ivr_survey_content = models.ForeignKey('scheduling.IVRSurveyContent', null=True, on_delete=models.CASCADE)
    custom_content = models.ForeignKey('scheduling.CustomContent', null=True, on_delete=models.CASCADE)

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
        elif self.custom_content_id:
            return self.custom_content

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
            SMSSurveyContent, IVRSurveyContent, CustomContent)

        self.sms_content = None
        self.email_content = None
        self.sms_survey_content = None
        self.ivr_survey_content = None
        self.custom_content = None

        if isinstance(value, SMSContent):
            self.sms_content = value
        elif isinstance(value, EmailContent):
            self.email_content = value
        elif isinstance(value, SMSSurveyContent):
            self.sms_survey_content = value
        elif isinstance(value, IVRSurveyContent):
            self.ivr_survey_content = value
        elif isinstance(value, CustomContent):
            self.custom_content = value
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

    @classmethod
    def get_one_way_phone_number(cls, recipient):
        phone_number = get_one_way_number_for_recipient(recipient)

        if not phone_number and isinstance(recipient, CommCareUser):
            if recipient.memoized_usercase:
                phone_number = get_one_way_number_for_recipient(recipient.memoized_usercase)

        if not phone_number or len(phone_number) <= 3:
            # Avoid processing phone numbers that are obviously fake to
            # save on processing time
            return None

        return phone_number

    @staticmethod
    def get_cleaned_message(message_dict, language_code):
        return message_dict.get(language_code, '').strip()

    @staticmethod
    def get_translation_from_message_dict(message_dict, schedule, preferred_language_code):
        """
        :param message_dict: a dictionary of {language code: message}
        :param schedule: an instance of corehq.messaging.scheduling.models.Schedule
        :param preferred_language_code: the language code of the user's preferred language
        """
        lang_doc = StandaloneTranslationDoc.get_obj(schedule.domain, 'sms')
        return (
            Content.get_cleaned_message(message_dict, preferred_language_code) or
            Content.get_cleaned_message(message_dict, schedule.default_language_code) or
            (Content.get_cleaned_message(message_dict, lang_doc.default_lang) if lang_doc else None) or
            Content.get_cleaned_message(message_dict, '*')
        )

    def send(self, recipient, schedule_instance):
        """
        :param recipient: a CommCareUser, WebUser, or CommCareCase/SQL
        representing the contact who should receive the content.
        """
        raise NotImplementedError()


class Broadcast(models.Model):
    domain = models.CharField(max_length=126, db_index=True)
    name = models.CharField(max_length=1000)
    last_sent_timestamp = models.DateTimeField(null=True)
    deleted = models.BooleanField(default=False)

    # A List of [recipient_type, recipient_id]
    recipients = jsonfield.JSONField(default=list)

    class Meta:
        abstract = True
