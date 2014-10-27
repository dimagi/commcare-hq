from django.utils.translation import ugettext_noop
from corehq.apps.reports.filters.base import BaseMultipleOptionFilter
from corehq.apps.sms.models import (
    WORKFLOW_REMINDER,
    WORKFLOW_KEYWORD,
    WORKFLOW_BROADCAST,
    WORKFLOW_CALLBACK,
    WORKFLOW_DEFAULT,
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
