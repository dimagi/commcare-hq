from django.utils.translation import ugettext_noop
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
    label = ugettext_noop("Message Type")
    default_text = ugettext_noop("Select Message Type...")
    slug = 'log_type'
    OPTION_SURVEY = 'survey'
    OPTION_OTHER = 'other'
    options = (
        (WORKFLOW_REMINDER, ugettext_noop('Reminder')),
        (WORKFLOW_KEYWORD, ugettext_noop('Keyword')),
        (WORKFLOW_BROADCAST, ugettext_noop('Broadcast')),
        (WORKFLOW_CALLBACK, ugettext_noop('Callback')),
        (OPTION_SURVEY, ugettext_noop('Survey')),
        (WORKFLOW_DEFAULT, ugettext_noop('Default')),
        (OPTION_OTHER, ugettext_noop('Other')),
    )


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
