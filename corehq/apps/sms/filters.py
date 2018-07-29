from __future__ import absolute_import
from __future__ import unicode_literals
from django.utils.translation import ugettext_noop, ugettext_lazy
from corehq.apps.es.groups import GroupES
from corehq.apps.reports.filters.base import BaseMultipleOptionFilter, BaseSingleOptionFilter, BaseReportFilter
from corehq.apps.reports.filters.base import BaseSimpleFilter
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


class PhoneNumberFilter(BaseSimpleFilter):
    slug = "phone_number"
    label = ugettext_lazy("Phone Number")
    help_inline = ugettext_lazy("Enter a full or partial phone number to filter results")


class RequiredPhoneNumberFilter(PhoneNumberFilter):
    @property
    def filter_context(self):
        context = super(RequiredPhoneNumberFilter, self).filter_context
        context['required'] = True
        return context


class PhoneNumberReportFilter(BaseReportFilter):
    label = ugettext_noop("Phone Number")
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
