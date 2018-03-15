from __future__ import absolute_import
from __future__ import unicode_literals
import jsonfield
import uuid
from memoized import memoized
from django.db import models, transaction
from corehq.apps.reminders.util import get_one_way_number_for_recipient
from corehq.apps.sms.api import MessageMetadata, send_sms
from corehq.apps.translations.models import StandaloneTranslationDoc
from corehq.apps.users.models import CommCareUser
from corehq.messaging.scheduling.exceptions import (
    NoAvailableContent,
    UnknownContentType,
)
from corehq.messaging.scheduling import util
from corehq.messaging.templating import (
    _get_obj_template_info,
    MessagingTemplateRenderer,
    SimpleDictTemplateParam,
    CaseMessagingTemplateParam,
)
from django.utils.functional import cached_property


class Schedule(models.Model):
    UI_TYPE_IMMEDIATE = 'I'
    UI_TYPE_DAILY = 'D'
    UI_TYPE_WEEKLY = 'W'
    UI_TYPE_MONTHLY = 'M'
    UI_TYPE_UNKNOWN = 'X'

    schedule_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    domain = models.CharField(max_length=126, db_index=True)
    active = models.BooleanField(default=True)
    deleted = models.BooleanField(default=False)

    # Only matters when the recipient of a ScheduleInstance is a Location
    # If False, only include users at that location as recipients
    # If True, include all users at that location or at any descendant locations as recipients
    include_descendant_locations = models.BooleanField(default=False)

    # If None, the list of languages defined in the project for messaging will be
    # inspected and the default language there will be used.
    default_language_code = models.CharField(max_length=126, null=True)

    # This metadata will be passed to any messages generated from this schedule.
    custom_metadata = jsonfield.JSONField(null=True, default=None)

    # One of the UI_TYPE_* constants describing the type of UI that should be used
    # to edit this schedule.
    ui_type = models.CharField(max_length=1, default=UI_TYPE_UNKNOWN)

    class Meta(object):
        abstract = True

    def set_first_event_due_timestamp(self, instance, start_date=None):
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

    @cached_property
    def memoized_uses_sms_survey(self):
        """
        Prefixed with memoized_ to make it obvious that this property is
        memoized and also relies on self.memoized_events.
        """
        from corehq.messaging.scheduling.models import SMSSurveyContent

        for event in self.memoized_events:
            if isinstance(event.content, SMSSurveyContent):
                return True

        return False

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

    class Meta(object):
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

    class Meta(object):
        abstract = True


class Content(models.Model):
    # If this this content is being invoked in the context of a case,
    # for example when a case triggers an alert, this is the case.
    case = None

    # If this content in being invoked in the context of a ScheduleInstance
    # (i.e., this was scheduled content), this is the ScheduleInstance.
    schedule_instance = None

    class Meta(object):
        abstract = True

    def set_context(self, case=None, schedule_instance=None):
        if case:
            self.case = case

        if schedule_instance:
            self.schedule_instance = schedule_instance

    @cached_property
    def case_rendering_context(self):
        """
        This is a cached property because many of the lookups done
        within a CaseMessagingTemplateParam are memoized, so by
        caching this return value we're able to reuse those lookups
        when looping over all expanded recipients of a ScheduleInstance.
        """
        if self.case:
            return CaseMessagingTemplateParam(self.case)

        return None

    def get_template_renderer(self, recipient):
        r = MessagingTemplateRenderer()
        r.set_context_param('recipient', SimpleDictTemplateParam(_get_obj_template_info(recipient)))

        if self.case_rendering_context:
            r.set_context_param('case', self.case_rendering_context)

        return r

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

    @memoized
    def get_lang_doc(self, domain):
        return StandaloneTranslationDoc.get_obj(domain, 'sms')

    def get_translation_from_message_dict(self, domain, message_dict, preferred_language_code):
        """
        :param domain: the domain
        :param message_dict: a dictionary of {language code: message}
        :param preferred_language_code: the language code of the user's preferred language
        """
        result = Content.get_cleaned_message(message_dict, preferred_language_code)

        if not result and self.schedule_instance:
            schedule = self.schedule_instance.memoized_schedule
            result = Content.get_cleaned_message(message_dict, schedule.default_language_code)

        if not result and self.get_lang_doc(domain):
            result = Content.get_cleaned_message(message_dict, self.get_lang_doc(domain).default_lang)

        if not result:
            result = Content.get_cleaned_message(message_dict, '*')

        return result

    def send(self, recipient, logged_event):
        """
        :param recipient: a CommCareUser, WebUser, or CommCareCase/SQL
        representing the contact who should receive the content.
        """
        raise NotImplementedError()

    def get_sms_message_metadata(self, logged_subevent):
        custom_metadata = {}

        if self.case:
            custom_metadata['case_id'] = self.case.case_id

        if self.schedule_instance and self.schedule_instance.memoized_schedule.custom_metadata:
            custom_metadata.update(self.schedule_instance.memoized_schedule.custom_metadata)

        return MessageMetadata(
            custom_metadata=custom_metadata,
            messaging_subevent_id=logged_subevent.pk,
        )

    def send_sms_message(self, domain, recipient, phone_number, message, logged_subevent):
        if not message:
            return

        metadata = self.get_sms_message_metadata(logged_subevent)
        send_sms(domain, recipient, phone_number, message, metadata=metadata)


class Broadcast(models.Model):
    domain = models.CharField(max_length=126, db_index=True)
    name = models.CharField(max_length=1000)
    last_sent_timestamp = models.DateTimeField(null=True)
    deleted = models.BooleanField(default=False)

    # A List of [recipient_type, recipient_id]
    recipients = jsonfield.JSONField(default=list)

    class Meta(object):
        abstract = True

    def soft_delete(self):
        raise NotImplementedError()
