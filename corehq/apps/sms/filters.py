from django.utils.translation import ugettext_noop, ugettext_lazy
from corehq import toggles
from corehq.apps.reports.filters.base import BaseMultipleOptionFilter, BaseSingleOptionFilter
from corehq.apps.reports.filters.search import SearchFilter
from corehq.apps.sms.models import (
    WORKFLOW_REMINDER,
    WORKFLOW_KEYWORD,
    WORKFLOW_BROADCAST,
    WORKFLOW_CALLBACK,
    WORKFLOW_PERFORMANCE,
    WORKFLOW_DEFAULT,
    MessagingEvent,
)


class MessageTypeFilter(BaseMultipleOptionFilter):
    label = ugettext_noop("Message Type")
    default_text = ugettext_noop("Select Message Type...")
    slug = 'log_type'
    OPTION_SURVEY = 'survey'
    OPTION_OTHER = 'other'

    @property
    def options(self):
        options_var = [
            (WORKFLOW_REMINDER, ugettext_noop('Reminder')),
            (WORKFLOW_KEYWORD, ugettext_noop('Keyword')),
            (WORKFLOW_BROADCAST, ugettext_noop('Broadcast')),
            (WORKFLOW_CALLBACK, ugettext_noop('Callback')),
            (self.OPTION_SURVEY, ugettext_noop('Survey')),
            (WORKFLOW_DEFAULT, ugettext_noop('Default')),
            (self.OPTION_OTHER, ugettext_noop('Other')),
        ]
        if toggles.SMS_PERFORMANCE_FEEDBACK.enabled(self.domain):
            options_var.insert(4, (WORKFLOW_PERFORMANCE, ugettext_noop('Performance messages'))),
        return options_var


class EventTypeFilter(BaseMultipleOptionFilter):
    label = ugettext_noop('Communication Type')
    default_text = ugettext_noop('Select Communication Type...')
    slug = 'event_type'
    options = [
        (MessagingEvent.SOURCE_BROADCAST, ugettext_noop('Broadcast')),
        (MessagingEvent.SOURCE_KEYWORD, ugettext_noop('Keyword')),
        (MessagingEvent.SOURCE_REMINDER, ugettext_noop('Reminder')),
        (MessagingEvent.CONTENT_SMS_SURVEY, ugettext_noop('Survey')),
        (MessagingEvent.CONTENT_SMS_CALLBACK, ugettext_noop('Callback')),
        (MessagingEvent.SOURCE_UNRECOGNIZED, ugettext_noop('Unrecognized')),
        (MessagingEvent.SOURCE_OTHER, ugettext_noop('Other')),
    ]
    default_options = [
        MessagingEvent.SOURCE_BROADCAST,
        MessagingEvent.SOURCE_KEYWORD,
        MessagingEvent.SOURCE_REMINDER,
        MessagingEvent.CONTENT_SMS_SURVEY,
    ]


class EventStatusFilter(BaseSingleOptionFilter):
    STATUS_CHOICES = (
        (MessagingEvent.STATUS_IN_PROGRESS, ugettext_noop('In Progress')),
        (MessagingEvent.STATUS_NOT_COMPLETED, ugettext_noop('Not Completed')),
        (MessagingEvent.STATUS_ERROR, ugettext_noop('Error')),
    )

    slug = 'event_status'
    label = ugettext_noop("Status")
    default_text = ugettext_noop("Any")
    options = STATUS_CHOICES


class PhoneNumberFilter(SearchFilter):
    label = ugettext_lazy("Phone Number")
    search_help_inline = ugettext_lazy("Enter a full or partial phone number to filter results")
