import jsonfield
import uuid
from memoized import memoized
from django.conf import settings
from django.db import models, transaction

from corehq import toggles
from corehq.apps.data_interfaces.utils import property_references_parent
from corehq.apps.reminders.util import get_one_way_number_for_recipient, get_two_way_number_for_recipient
from corehq.apps.sms.api import MessageMetadata, send_sms, send_sms_to_verified_number
from corehq.apps.sms.forms import (
    LANGUAGE_FALLBACK_NONE,
    LANGUAGE_FALLBACK_SCHEDULE,
    LANGUAGE_FALLBACK_DOMAIN,
)
from corehq.apps.sms.models import (
    MessagingEvent,
    PhoneNumber,
    WORKFLOW_REMINDER,
    WORKFLOW_KEYWORD,
    WORKFLOW_BROADCAST,
)
from corehq.apps.translations.models import SMSTranslations
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
    UI_TYPE_CUSTOM_DAILY = 'CD'
    UI_TYPE_CUSTOM_IMMEDIATE = 'CI'
    UI_TYPE_UNKNOWN = 'X'

    schedule_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    domain = models.CharField(max_length=126, db_index=True)
    active = models.BooleanField(default=True)
    deleted = models.BooleanField(default=False)
    deleted_on = models.DateTimeField(null=True)

    # Only matters when the recipient of a ScheduleInstance is a Location
    # If False, only include users at that location as recipients
    # If True, include all users at that location or at any descendant locations as recipients
    include_descendant_locations = models.BooleanField(default=False)

    # Only matters when include_descendant_locations is True.
    # If this is an empty list, it's ignored.
    # Otherwise, only the SQLLocations whose LocationType foreign keys are in this list
    # will be considered when expanding the recipients of the schedule instance.
    location_type_filter = jsonfield.JSONField(default=list)

    # If None, the list of languages defined in the project for messaging will be
    # inspected and the default language there will be used.
    default_language_code = models.CharField(max_length=126, null=True)

    # This metadata will be passed to any messages generated from this schedule.
    custom_metadata = jsonfield.JSONField(null=True, default=None)

    # One of the UI_TYPE_* constants describing the type of UI that should be used
    # to edit this schedule.
    ui_type = models.CharField(max_length=2, default=UI_TYPE_UNKNOWN)

    #   The old reminders framework would interpret times using UTC if the contact
    # didn't have a time zone configured. The new reminders framework uses the
    # project's time zone if the contact doesn't have a time zone configured.
    #   There are a lot of edge cases which make it not possible to just convert
    # times in reminders during the reminders migration. So for old reminders
    # where this makes a difference, this option is set to True during the migration.
    use_utc_as_default_timezone = models.BooleanField(default=False)

    #   If {}, this option will be ignored.
    #   Otherwise, for each recipient in the recipient list that is a CouchUser,
    # that recipient's custom user data will be checked against this option to
    # determine if the recipient should stay in the recipient list or not.
    #   This should be a dictionary where each key is the name of a custom user data
    # field, and each value is a list of allowed values for that field.
    #   For example, if this is set to: {'nickname': ['bob', 'jim'], 'phone_type': ['android']}
    # then the recipient list would be filtered to only include users whose phone
    # type is android and whose nickname is either bob or jim.
    user_data_filter = jsonfield.JSONField(default=dict)

    #   Only applies when this Schedule is used with CaseAlertScheduleInstances or
    # CaseTimedScheduleInstances.
    #   If null, this is ignored. Otherwise, it's the name of a case property which
    # can be used to set a stop date for the schedule. If the case property doesn't
    # reference a date (e.g., it's blank), then there's no effect. But if it references
    # a date then the corresponding schedule instance will be deactivated once the
    # framework realizes that date has passed.
    stop_date_case_property_name = models.CharField(max_length=126, null=True)

    class Meta(object):
        abstract = True

    @classmethod
    def assert_is(cls, schedule):
        if not isinstance(schedule, cls):
            raise TypeError("Expected " + cls.__name__)

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

    def set_next_event_due_timestamp(self, instance):
        raise NotImplementedError()

    def move_to_next_event_not_in_the_past(self, instance):
        while instance.active and instance.next_event_due < util.utcnow():
            self.move_to_next_event(instance)

    def get_extra_scheduling_options(self):
        return {
            'active': self.active,
            'default_language_code': self.default_language_code,
            'include_descendant_locations': self.include_descendant_locations,
            'location_type_filter': self.location_type_filter,
            'use_utc_as_default_timezone': self.use_utc_as_default_timezone,
            'user_data_filter': self.user_data_filter,
        }

    def set_extra_scheduling_options(self, options):
        if not options:
            return

        for k, v in options.items():
            setattr(self, k, v)

    @property
    @memoized
    def memoized_language_set(self):
        from corehq.messaging.scheduling.models import SMSContent, EmailContent, SMSCallbackContent

        result = set()
        for event in self.memoized_events:
            content = event.memoized_content
            if isinstance(content, (SMSContent, SMSCallbackContent)):
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

    @cached_property
    def memoized_uses_ivr_survey(self):
        """
        Prefixed with memoized_ to make it obvious that this property is
        memoized and also relies on self.memoized_events.
        """
        from corehq.messaging.scheduling.models import IVRSurveyContent

        for event in self.memoized_events:
            if isinstance(event.content, IVRSurveyContent):
                return True

        return False

    @cached_property
    def memoized_uses_sms_callback(self):
        """
        Prefixed with memoized_ to make it obvious that this property is
        memoized and also relies on self.memoized_events.
        """
        from corehq.messaging.scheduling.models import SMSCallbackContent

        for event in self.memoized_events:
            if isinstance(event.content, SMSCallbackContent):
                return True

        return False

    @property
    def references_parent_case(self):
        if self.stop_date_case_property_name and property_references_parent(self.stop_date_case_property_name):
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
    sms_callback_content = models.ForeignKey('scheduling.SMSCallbackContent', null=True, on_delete=models.CASCADE)
    fcm_notification_content = models.ForeignKey('scheduling.FCMNotificationContent', null=True,
                                                 on_delete=models.CASCADE)

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
        elif self.sms_callback_content_id:
            return self.sms_callback_content
        elif self.fcm_notification_content:
            return self.fcm_notification_content

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
            SMSSurveyContent, IVRSurveyContent, CustomContent, SMSCallbackContent, FCMNotificationContent)

        self.sms_content = None
        self.email_content = None
        self.sms_survey_content = None
        self.ivr_survey_content = None
        self.custom_content = None
        self.sms_callback_content = None

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
        elif isinstance(value, SMSCallbackContent):
            self.sms_callback_content = value
        elif isinstance(value, FCMNotificationContent):
            self.fcm_notification_content = value
        else:
            raise UnknownContentType()


class Event(ContentForeignKeyMixin):
    # Order is only used for sorting the events in a schedule. Convention
    # dictates that it should start with 1 and be sequential, but technically
    # it doesn't matter as long as it sorts the events properly.
    order = models.IntegerField()

    class Meta(object):
        abstract = True

    def create_copy(self):
        """
        The point of this method is to create a copy of this object with no
        primary keys set or references to other objects. It's used in the
        process of copying schedules to a different project in the copy
        conditional alert workflow, so there should also not be any
        unresolved project-specific references in the returned copy.
        """
        raise NotImplementedError()


class Content(models.Model):
    # If this this content is being invoked in the context of a case,
    # for example when a case triggers an alert, this is the case.
    case = None

    # If this content in being invoked in the context of a ScheduleInstance
    # (i.e., this was scheduled content), this is the ScheduleInstance.
    schedule_instance = None

    # Set to True if any necessary critical section locks have
    # already been acquired. This is currently only used for SMSSurveyContent
    # under certain circumstances.
    critical_section_already_acquired = False

    class Meta(object):
        abstract = True

    def create_copy(self):
        """
        The point of this method is to create a copy of this object with no
        primary keys set or references to other objects. It's used in the
        process of copying schedules to a different project in the copy
        conditional alert workflow, so there should also not be any
        unresolved project-specific references in the returned copy.
        """
        raise NotImplementedError()

    def set_context(self, case=None, schedule_instance=None, critical_section_already_acquired=False):
        if case:
            self.case = case

        if schedule_instance:
            self.schedule_instance = schedule_instance

        self.critical_section_already_acquired = critical_section_already_acquired

    @staticmethod
    def get_workflow(logged_event):
        if logged_event.source in (
            MessagingEvent.SOURCE_IMMEDIATE_BROADCAST,
            MessagingEvent.SOURCE_SCHEDULED_BROADCAST,
        ):
            return WORKFLOW_BROADCAST
        elif logged_event.source == MessagingEvent.SOURCE_CASE_RULE:
            return WORKFLOW_REMINDER
        elif logged_event.source == MessagingEvent.SOURCE_KEYWORD:
            return WORKFLOW_KEYWORD

        return None

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
    def get_two_way_entry_or_phone_number(cls, recipient, try_usercase=True, domain_for_toggles=None):
        """
        If recipient has a two-way number, returns it as a PhoneNumber entry.
        If recipient does not have a two-way number but has a phone number configured,
        returns the one-way phone number as a string.

        If try_usercase is True and recipient is a CommCareUser who doesn't have a
        two-way or one-way phone number, then it will try to get the two-way or
        one-way number from the user's user case if one exists.
        """
        if settings.USE_PHONE_ENTRIES:
            phone_entry = get_two_way_number_for_recipient(recipient)
            if phone_entry:
                return phone_entry

        phone_number = get_one_way_number_for_recipient(recipient)

        if toggles.INBOUND_SMS_LENIENCY.enabled(domain_for_toggles) and \
                toggles.ONE_PHONE_NUMBER_MULTIPLE_CONTACTS.enabled(domain_for_toggles):
            phone_entry = PhoneNumber.get_phone_number_for_owner(recipient.get_id, phone_number)
            if phone_entry:
                return phone_entry

        # Avoid processing phone numbers that are obviously fake (len <= 3) to
        # save on processing time
        if phone_number and len(phone_number) > 3:
            return phone_number

        if try_usercase and isinstance(recipient, CommCareUser) and recipient.memoized_usercase:
            return cls.get_two_way_entry_or_phone_number(recipient.memoized_usercase,
                                                         domain_for_toggles=domain_for_toggles)

        return None

    @staticmethod
    def get_cleaned_message(message_dict, language_code):
        return message_dict.get(language_code, '').strip()

    @memoized
    def get_default_lang(self, domain):
        return SMSTranslations.objects.filter(domain=domain).first().default_lang

    def get_translation_from_message_dict(self, domain_obj, message_dict, preferred_language_code):
        """
        Attempt to get translated content. If content is not available in the user's preferred language,
        attempt to fall back to other languages, as allowed by domain setting sms_language_fallback.

        By default, try all possible fallbacks before giving up (same as LANGUAGE_FALLBACK_UNTRANSLATED).

        :param domain_obj: the domain object
        :param message_dict: a dictionary of {language code: message}
        :param preferred_language_code: the language code of the user's preferred language
        """

        # return untranslated content, if no translations set
        if {'*'} == message_dict.keys():
            return Content.get_cleaned_message(message_dict, '*')

        result = Content.get_cleaned_message(message_dict, preferred_language_code)

        if domain_obj.sms_language_fallback == LANGUAGE_FALLBACK_NONE:
            return result

        if not result and self.schedule_instance:
            schedule = self.schedule_instance.memoized_schedule
            result = Content.get_cleaned_message(message_dict, schedule.default_language_code)

        if domain_obj.sms_language_fallback == LANGUAGE_FALLBACK_SCHEDULE:
            return result

        if not result:
            lang = self.get_default_lang(domain_obj.name)
            result = Content.get_cleaned_message(message_dict, lang)

        if domain_obj.sms_language_fallback == LANGUAGE_FALLBACK_DOMAIN:
            return result

        if not result:
            result = Content.get_cleaned_message(message_dict, '*')

        return result

    def send(self, recipient, logged_event, phone_entry=None):
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

    def send_sms_message(self, domain, recipient, phone_entry_or_number, message, logged_subevent):
        if not message:
            return

        metadata = self.get_sms_message_metadata(logged_subevent)

        if isinstance(phone_entry_or_number, PhoneNumber):
            send_sms_to_verified_number(phone_entry_or_number, message, metadata=metadata,
                logged_subevent=logged_subevent)
        else:
            send_sms(domain, recipient, phone_entry_or_number, message, metadata=metadata,
                logged_subevent=logged_subevent)


class Broadcast(models.Model):
    domain = models.CharField(max_length=126, db_index=True)
    name = models.CharField(max_length=1000)
    last_sent_timestamp = models.DateTimeField(null=True)
    deleted = models.BooleanField(default=False)
    deleted_on = models.DateTimeField(null=True)

    # A List of [recipient_type, recipient_id]
    recipients = jsonfield.JSONField(default=list)

    class Meta(object):
        abstract = True

    def soft_delete(self):
        raise NotImplementedError()

    @classmethod
    def domain_has_broadcasts(cls, domain):
        return cls.objects.filter(domain=domain, deleted=False).exists()
