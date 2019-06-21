from __future__ import absolute_import, unicode_literals

import cgi
from collections import namedtuple

from django.urls import reverse
from django.utils.translation import ugettext as _

from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.sms.models import (
    INCOMING,
    OUTGOING,
    SMS,
    WORKFLOW_FORWARD,
    Keyword,
    MessagingEvent,
    MessagingSubEvent,
)
from corehq.messaging.scheduling.models import (
    ImmediateBroadcast,
    MigratedReminder,
    ScheduledBroadcast,
)
from corehq.messaging.scheduling.views import (
    EditConditionalAlertView,
    EditScheduleView,
)


def get_status_display(event, sms=None):
    """
    event can be a MessagingEvent or MessagingSubEvent
    """
    # If sms without error, short circuit to the sms status display
    if event.status != MessagingEvent.STATUS_ERROR and sms:
        return get_sms_status_display(sms)

    # If survey without error, short circuit to the survey status display
    if (isinstance(event, MessagingSubEvent) and
            event.status == MessagingEvent.STATUS_COMPLETED and
            event.xforms_session_id):
        return _(event.xforms_session.status)

    status = event.status
    error_code = event.error_code

    # If we have a MessagingEvent with no error_code it means there's
    # an error in the subevent
    if status == MessagingEvent.STATUS_ERROR and not error_code:
        error_code = MessagingEvent.ERROR_SUBEVENT_ERROR

    # If we have a MessagingEvent that's completed but it's tied to
    # unfinished surveys, then mark it as being in progress
    if (
        isinstance(event, MessagingEvent) and
        event.status == MessagingEvent.STATUS_COMPLETED and
        MessagingSubEvent.objects.filter(
            parent_id=event.pk,
            content_type=MessagingEvent.CONTENT_SMS_SURVEY,
            # without this line, django does a left join which is not what we want
            xforms_session_id__isnull=False,
            xforms_session__session_is_open=True
        ).count() > 0
    ):
        status = MessagingEvent.STATUS_IN_PROGRESS

    status = dict(MessagingEvent.STATUS_CHOICES).get(status, '-')
    error_message = (MessagingEvent.ERROR_MESSAGES.get(error_code, None)
                     if error_code else None)
    error_message = _(error_message) if error_message else ''
    if event.additional_error_text:
        error_message += ' %s' % event.additional_error_text

    # Sometimes the additional information from touchforms has < or >
    # characters, so we need to escape them for display
    if error_message:
        return '%s - %s' % (_(status), cgi.escape(error_message))
    else:
        return _(status)


def get_sms_status_display(sms):
    if sms.error:
        error_message = (SMS.ERROR_MESSAGES.get(sms.system_error_message, None)
                         if sms.system_error_message else None)
        if error_message:
            return '%s - %s' % (_('Error'), _(error_message))
        else:
            return _('Error')
    elif not sms.processed:
        return _('Queued')
    else:
        if sms.direction == INCOMING:
            return _('Received')
        elif sms.direction == OUTGOING:
            if sms.workflow == WORKFLOW_FORWARD:
                return _('Forwarded')
            else:
                return _('Sent')
        else:
            return _('Unknown')


def _get_keyword_display(keyword_id, content_cache):
    from corehq.apps.reminders.views import (
        EditStructuredKeywordView,
        EditNormalKeywordView,
    )
    if keyword_id in content_cache:
        return content_cache[keyword_id]

    try:
        keyword = Keyword.objects.get(couch_id=keyword_id)
    except Keyword.DoesNotExist:
        display = _('(Deleted Keyword)')
    else:
        urlname = (EditStructuredKeywordView.urlname if keyword.is_structured_sms()
                   else EditNormalKeywordView.urlname)
        display = '<a target="_blank" href="%s">%s</a>' % (
            reverse(urlname, args=[keyword.domain, keyword_id]),
            keyword.description,
        )

    content_cache[keyword_id] = display
    return display


def _get_reminder_display(domain, handler_id, content_cache):
    if handler_id in content_cache:
        return content_cache[handler_id]

    display = None

    try:
        info = MigratedReminder.objects.get(handler_id=handler_id)
        if info.rule_id:
            display = _get_case_rule_display(domain, info.rule_id, content_cache)
    except MigratedReminder.DoesNotExist:
        pass

    if not display:
        display = _("(Deleted Conditional Alert)")

    content_cache[handler_id] = display
    return display


def _get_scheduled_broadcast_display(domain, broadcast_id, content_cache):
    cache_key = 'scheduled-broadcast-%s' % broadcast_id
    if cache_key in content_cache:
        return content_cache[cache_key]

    try:
        broadcast = ScheduledBroadcast.objects.get(domain=domain, pk=broadcast_id)
    except ScheduledBroadcast.DoesNotExist:
        result = '-'
    else:
        if broadcast.deleted:
            result = _("(Deleted Broadcast)")
        else:
            result = '<a target="_blank" href="%s">%s</a>' % (
                reverse(EditScheduleView.urlname,
                        args=[domain, EditScheduleView.SCHEDULED_BROADCAST, broadcast_id]),
                broadcast.name,
            )

    content_cache[cache_key] = result
    return result


def _get_immediate_broadcast_display(domain, broadcast_id, content_cache):
    cache_key = 'immediate-broadcast-%s' % broadcast_id
    if cache_key in content_cache:
        return content_cache[cache_key]

    try:
        broadcast = ImmediateBroadcast.objects.get(domain=domain, pk=broadcast_id)
    except ImmediateBroadcast.DoesNotExist:
        result = '-'
    else:
        if broadcast.deleted:
            result = _("(Deleted Broadcast)")
        else:
            result = '<a target="_blank" href="%s">%s</a>' % (
                reverse(EditScheduleView.urlname,
                        args=[domain, EditScheduleView.IMMEDIATE_BROADCAST, broadcast_id]),
                broadcast.name,
            )

    content_cache[cache_key] = result
    return result


def _get_case_rule_display(domain, rule_id, content_cache):
    cache_key = 'case-rule-%s' % rule_id
    if cache_key in content_cache:
        return content_cache[cache_key]

    try:
        rule = AutomaticUpdateRule.objects.get(domain=domain, pk=rule_id)
    except AutomaticUpdateRule.DoesNotExist:
        result = '-'
    else:
        if rule.deleted:
            result = _("(Deleted Conditional Alert)")
        else:
            result = '<a target="_blank" href="%s">%s</a>' % (
                reverse(EditConditionalAlertView.urlname,
                        args=[domain, rule_id]),
                rule.name,
            )

    content_cache[cache_key] = result
    return result


EventStub = namedtuple('EventStub', 'source source_id content_type form_name')


def get_event_display(domain, event, content_cache):
    if event.source == MessagingEvent.SOURCE_KEYWORD and event.source_id:
        return _get_keyword_display(event.source_id, content_cache)
    elif event.source == MessagingEvent.SOURCE_REMINDER and event.source_id:
        return _get_reminder_display(domain, event.source_id, content_cache)
    elif event.source == MessagingEvent.SOURCE_SCHEDULED_BROADCAST and event.source_id:
        return _get_scheduled_broadcast_display(domain, event.source_id, content_cache)
    elif event.source == MessagingEvent.SOURCE_IMMEDIATE_BROADCAST and event.source_id:
        return _get_immediate_broadcast_display(domain, event.source_id, content_cache)
    elif event.source == MessagingEvent.SOURCE_CASE_RULE and event.source_id:
        return _get_case_rule_display(domain, event.source_id, content_cache)
    elif event.content_type in (
        MessagingEvent.CONTENT_SMS_SURVEY,
        MessagingEvent.CONTENT_IVR_SURVEY,
    ):
        return ('%s (%s)' % (_(dict(MessagingEvent.CONTENT_CHOICES).get(event.content_type)),
                             event.form_name or _('Unknown')))

    content_choices = dict(MessagingEvent.CONTENT_CHOICES)
    return _(content_choices.get(event.content_type, '-'))
