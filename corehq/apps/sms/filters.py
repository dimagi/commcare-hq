from django.utils.translation import ugettext_lazy
from corehq.apps.reports.filters.base import BaseMultipleOptionFilter
from corehq.apps.sms.models import (
    WORKFLOW_REMINDER,
    WORKFLOW_KEYWORD,
    WORKFLOW_BROADCAST,
    WORKFLOW_CALLBACK,
    WORKFLOW_DEFAULT,
    MessagingEvent,
)


class MessageTypeFilter(BaseMultipleOptionFilter):
    label = ugettext_lazy("Message Type")
    default_text = ugettext_lazy("Select Message Type...")
    slug = 'log_type'
    OPTION_SURVEY = 'survey'
    OPTION_OTHER = 'other'
    options = (
        (WORKFLOW_REMINDER, ugettext_lazy('Reminder')),
        (WORKFLOW_KEYWORD, ugettext_lazy('Keyword')),
        (WORKFLOW_BROADCAST, ugettext_lazy('Broadcast')),
        (WORKFLOW_CALLBACK, ugettext_lazy('Callback')),
        (OPTION_SURVEY, ugettext_lazy('Survey')),
        (WORKFLOW_DEFAULT, ugettext_lazy('Default')),
        (OPTION_OTHER, ugettext_lazy('Other')),
    )


class EventTypeFilter(BaseMultipleOptionFilter):
    label = ugettext_lazy('Communication Type')
    default_text = ugettext_lazy('Select Communication Type...')
    slug = 'event_type'
    options = [
        (MessagingEvent.SOURCE_BROADCAST, ugettext_lazy('Broadcast')),
        (MessagingEvent.SOURCE_KEYWORD, ugettext_lazy('Keyword')),
        (MessagingEvent.SOURCE_REMINDER, ugettext_lazy('Reminder')),
        (MessagingEvent.CONTENT_SMS_SURVEY, ugettext_lazy('Survey')),
        (MessagingEvent.CONTENT_SMS_CALLBACK, ugettext_lazy('Callback')),
        (MessagingEvent.SOURCE_UNRECOGNIZED, ugettext_lazy('Unrecognized')),
        (MessagingEvent.SOURCE_OTHER, ugettext_lazy('Other')),
    ]
    default_options = [
        MessagingEvent.SOURCE_BROADCAST,
        MessagingEvent.SOURCE_KEYWORD,
        MessagingEvent.SOURCE_REMINDER,
        MessagingEvent.CONTENT_SMS_SURVEY,
    ]
