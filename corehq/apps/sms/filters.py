from django.utils.translation import gettext_lazy, gettext_noop

from corehq.apps.es.groups import GroupES
from corehq.apps.reports.filters.base import (
    BaseMultipleOptionFilter,
    BaseReportFilter,
    BaseSimpleFilter,
    BaseSingleOptionFilter,
)
from corehq.apps.sms.models import (
    WORKFLOW_BROADCAST,
    WORKFLOW_CALLBACK,
    WORKFLOW_DEFAULT,
    WORKFLOW_KEYWORD,
    WORKFLOW_REMINDER,
    MessagingEvent,
)


class MessageTypeFilter(BaseMultipleOptionFilter):
    label = gettext_noop("Message Type")
    default_text = gettext_noop("Select Message Type...")
    slug = 'log_type'
    OPTION_SURVEY = 'survey'
    OPTION_OTHER = 'other'

    @property
    def options(self):
        options_var = [
            (WORKFLOW_REMINDER, gettext_noop('Reminder')),
            (WORKFLOW_KEYWORD, gettext_noop('Keyword')),
            (WORKFLOW_BROADCAST, gettext_noop('Broadcast')),
            (WORKFLOW_CALLBACK, gettext_noop('Callback')),
            (self.OPTION_SURVEY, gettext_noop('Survey')),
            (WORKFLOW_DEFAULT, gettext_noop('Default')),
            (self.OPTION_OTHER, gettext_noop('Other')),
        ]
        return options_var


class ErrorCodeFilter(BaseMultipleOptionFilter):
    label = gettext_noop('Error')
    default_text = gettext_noop('Select Error...')
    slug = 'error_code'

    options = [
        (code, message.split(".")[0])   # shorten multi-sentence messages
        for code, message in MessagingEvent.ERROR_MESSAGES.items()
        if code != MessagingEvent.ERROR_SUBEVENT_ERROR
    ]


class EventTypeFilter(BaseMultipleOptionFilter):
    label = gettext_noop('Communication Type')
    default_text = gettext_noop('Select Communication Type...')
    slug = 'event_type'
    options = [
        (MessagingEvent.SOURCE_BROADCAST, gettext_noop('Broadcast')),
        (MessagingEvent.SOURCE_KEYWORD, gettext_noop('Keyword')),
        (MessagingEvent.SOURCE_REMINDER, gettext_noop('Conditional Alert')),
        (MessagingEvent.SOURCE_UNRECOGNIZED, gettext_noop('Unrecognized')),
        (MessagingEvent.SOURCE_OTHER, gettext_noop('Other')),
    ]
    default_options = [
        MessagingEvent.SOURCE_BROADCAST,
        MessagingEvent.SOURCE_KEYWORD,
        MessagingEvent.SOURCE_REMINDER,
    ]


class EventContentFilter(BaseMultipleOptionFilter):
    label = gettext_noop('Content Type')
    default_text = gettext_noop('All')
    slug = 'content_type'

    @property
    def options(self):
        return [
            (MessagingEvent.CONTENT_SMS_SURVEY, gettext_noop('SMS Survey')),
            (MessagingEvent.CONTENT_SMS_CALLBACK, gettext_noop('SMS Callback')),
            (MessagingEvent.CONTENT_SMS, gettext_noop('Other SMS')),
            (MessagingEvent.CONTENT_EMAIL, gettext_noop('Email')),
            (MessagingEvent.CONTENT_CONNECT, gettext_noop('Connect Message')),
        ]


class EventStatusFilter(BaseSingleOptionFilter):
    STATUS_CHOICES = (
        (MessagingEvent.STATUS_IN_PROGRESS, gettext_noop('In Progress')),
        (MessagingEvent.STATUS_NOT_COMPLETED, gettext_noop('Not Completed')),
        (MessagingEvent.STATUS_ERROR, gettext_noop('Error')),
        (MessagingEvent.STATUS_EMAIL_DELIVERED, gettext_noop('Delivered (Email Only)')),
    )

    slug = 'event_status'
    label = gettext_noop("Status")
    default_text = gettext_noop("Any")
    options = STATUS_CHOICES


class PhoneNumberFilter(BaseSimpleFilter):
    slug = "phone_number"
    label = gettext_lazy("Phone Number")
    help_inline = gettext_lazy("Enter a full or partial phone number to filter results")


class RequiredPhoneNumberFilter(PhoneNumberFilter):
    @property
    def filter_context(self):
        context = super(RequiredPhoneNumberFilter, self).filter_context
        context['required'] = True
        return context


class PhoneNumberOrEmailFilter(BaseSimpleFilter):
    slug = "phone_number_or_email_address"
    label = gettext_lazy("Phone Number or Email Address")
    help_inline = gettext_lazy("Enter a full or partial phone number or a full or partial email "
                               "address to filter results")


class PhoneNumberReportFilter(BaseReportFilter):
    label = gettext_noop("Phone Number")
    slug = "phone_number_filter"
    template = "sms/phone_number_filter.html"

    @property
    def filter_context(self):
        return {
            "initial_value": self.get_value(self.request, self.domain),
            "groups": [{'_id': '', 'name': ''}] + GroupES().domain(self.domain).source(['_id', 'name']).run().hits,
        }

    @classmethod
    def get_value(cls, request, domain):
        return {
            'filter_type': request.GET.get('filter_type'),
            'phone_number_filter': request.GET.get('phone_number_filter'),
            'contact_type': request.GET.get('contact_type'),
            'selected_group': request.GET.get('selected_group'),
            'has_phone_number': request.GET.get('has_phone_number'),
            'verification_status': request.GET.get('verification_status'),
        }
