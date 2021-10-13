import cgi
from collections import namedtuple

from django.urls import reverse
from django.utils.html import format_html
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
from corehq.util.quickcache import quickcache


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
    slug, detail = get_sms_status_display_raw(sms)
    display = SMS.STATUS_DISPLAY[slug]
    detail = f" - {detail}" if detail else ""
    return f"{display}{detail}"


def get_sms_status_display_raw(sms):
    if sms.error:
        error = sms.system_error_message
        if error:
            error_message = SMS.ERROR_MESSAGES.get(error, error)
            return SMS.STATUS_ERROR, _(error_message)
        return SMS.STATUS_ERROR, None
    if not sms.processed:
        return SMS.STATUS_QUEUED, None
    if sms.direction == INCOMING:
        return SMS.STATUS_RECEIVED, None

    detail = ""
    if sms.is_status_pending():
        detail = _("message ID: {id}").format(id=sms.backend_message_id)

    if sms.direction == OUTGOING:
        if sms.workflow == WORKFLOW_FORWARD:
            return SMS.STATUS_FORWARDED, detail
        if sms.custom_metadata and sms.custom_metadata.get('gateway_delivered', False):
            return SMS.STATUS_DELIVERED, detail
        return SMS.STATUS_SENT, detail
    return SMS.STATUS_UNKNOWN, detail


def _get_keyword_display_raw(keyword_id):
    from corehq.apps.reminders.views import (
        EditStructuredKeywordView,
        EditNormalKeywordView,
    )
    try:
        keyword = Keyword.objects.get(couch_id=keyword_id)
    except Keyword.DoesNotExist:
        return None, None

    urlname = (EditStructuredKeywordView.urlname if keyword.is_structured_sms()
               else EditNormalKeywordView.urlname)
    return keyword.description, reverse(urlname, args=[keyword.domain, keyword_id])


def _get_keyword_display(keyword_id, content_cache):
    if keyword_id in content_cache:
        return content_cache[keyword_id]

    display, url = _get_keyword_display_raw(keyword_id)
    if not display:
        display = _('(Deleted Keyword)')
    else:
        display = format_html('<a target="_blank" href="{}">{}</a>', url, display)

    content_cache[keyword_id] = display
    return display


def _get_reminder_display_raw(domain, handler_id):
    try:
        info = MigratedReminder.objects.get(handler_id=handler_id)
        if info.rule_id:
            return _get_case_rule_display_raw(domain, info.rule_id)
    except MigratedReminder.DoesNotExist:
        pass
    return None, None


def _get_reminder_display(domain, handler_id, content_cache):
    if handler_id in content_cache:
        return content_cache[handler_id]

    result, url = _get_reminder_display_raw(domain, handler_id)
    if not result:
        result = _("(Deleted Conditional Alert)")
    elif url:
        result = format_html('<a target="_blank" href="{}">{}</a>', url, result)

    content_cache[handler_id] = result
    return result


def _get_scheduled_broadcast_display_raw(domain, broadcast_id):
    try:
        broadcast = ScheduledBroadcast.objects.get(domain=domain, pk=broadcast_id)
    except ScheduledBroadcast.DoesNotExist:
        return "-", None

    if not broadcast.deleted:
        return broadcast.name, reverse(EditScheduleView.urlname, args=[
            domain, EditScheduleView.SCHEDULED_BROADCAST, broadcast_id
        ])
    return None, None


def _get_scheduled_broadcast_display(domain, broadcast_id, content_cache):
    cache_key = 'scheduled-broadcast-%s' % broadcast_id
    if cache_key in content_cache:
        return content_cache[cache_key]

    result, url = _get_scheduled_broadcast_display_raw(domain, broadcast_id)
    if not result:
        result = _("(Deleted Broadcast)")
    elif url:
        result = format_html('<a target="_blank" href="{}">{}</a>', url, result)

    content_cache[cache_key] = result
    return result


def _get_immediate_broadcast_display_raw(domain, broadcast_id):
    try:
        broadcast = ImmediateBroadcast.objects.get(domain=domain, pk=broadcast_id)
    except ImmediateBroadcast.DoesNotExist:
        return '-', None

    if not broadcast.deleted:
        return broadcast.name, reverse(EditScheduleView.urlname, args=[
            domain, EditScheduleView.IMMEDIATE_BROADCAST, broadcast_id
        ])
    return None, None


def _get_immediate_broadcast_display(domain, broadcast_id, content_cache):
    cache_key = 'immediate-broadcast-%s' % broadcast_id
    if cache_key in content_cache:
        return content_cache[cache_key]

    result, url = _get_immediate_broadcast_display_raw(domain, broadcast_id)
    if not result:
        result = _("(Deleted Broadcast)")
    elif url:
        result = format_html('<a target="_blank" href="{}">{}</a>', url, result)

    content_cache[cache_key] = result
    return result


def _get_case_rule_display_raw(domain, rule_id):
    try:
        rule = AutomaticUpdateRule.objects.get(domain=domain, pk=rule_id)
    except AutomaticUpdateRule.DoesNotExist:
        return "-", None

    if not rule.deleted:
        return rule.name, reverse(EditConditionalAlertView.urlname, args=[domain, rule_id])
    return None, None


def _get_case_rule_display(domain, rule_id, content_cache):
    cache_key = 'case-rule-%s' % rule_id
    if cache_key in content_cache:
        return content_cache[cache_key]

    result, url = _get_case_rule_display_raw(domain, rule_id)
    if not result:
        result = _("(Deleted Conditional Alert)")
    elif url:
        result = format_html('<a target="_blank" href="{}">{}</a>', url, result)
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


@quickcache(["domain", "source", "source_id"], timeout=5 * 60)
def get_source_display(domain, source, source_id):
    if not source_id:
        return None

    if source == MessagingEvent.SOURCE_KEYWORD:
        display, _ = _get_keyword_display_raw(source_id)
        return display or "deleted-keyword"
    elif source == MessagingEvent.SOURCE_REMINDER:
        display, _ = _get_reminder_display_raw(domain, source_id)
        return display or "deleted-conditional-alert"
    elif source == MessagingEvent.SOURCE_SCHEDULED_BROADCAST:
        display, _ = _get_scheduled_broadcast_display_raw(domain, source_id)
        return display or "deleted-broadcast"
    elif source == MessagingEvent.SOURCE_IMMEDIATE_BROADCAST:
        display, _ = _get_immediate_broadcast_display_raw(domain, source_id)
        return display or "deleted-broadcast"
    elif source == MessagingEvent.SOURCE_CASE_RULE:
        display, _ = _get_case_rule_display_raw(domain, source_id)
        return display or "deleted-conditional-alert"

    return None


def get_event_display_api(event):
    if event.source_id:
        source_display = get_source_display(event.domain, event.source, event.source_id)
        if source_display:
            return source_display

    detail = ""
    if event.content_type in (
        MessagingEvent.CONTENT_SMS_SURVEY,
        MessagingEvent.CONTENT_IVR_SURVEY,
    ):
        form_name = event.form_name or "unknown-form"
        detail = f" ({form_name})"

    type_ = MessagingEvent.CONTENT_TYPE_SLUGS.get(event.content_type, "unknown")
    return f"{type_}{detail}"
