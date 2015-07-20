import cgi
from django.db.models import Q
from django.core.urlresolvers import reverse
from django.http import Http404
from django.utils.translation import ugettext_lazy
from django.utils.translation import ugettext as _
from couchdbkit.resource import ResourceNotFound
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.standard import DatespanMixin, ProjectReport,\
    ProjectReportParametersMixin
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader,\
    DTSortType
from corehq.apps.sms.filters import MessageTypeFilter, EventTypeFilter
from corehq.const import SERVER_DATETIME_FORMAT
from corehq.util.timezones.conversions import ServerTime
from corehq.util.view_utils import absolute_reverse
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.parsing import json_format_datetime
from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.groups.models import Group
from corehq.apps.reports.util import format_datatables_data
from corehq.apps.users.models import CouchUser
from casexml.apps.case.models import CommCareCase
from django.conf import settings
# This import is not used, but there's some sort circular dependency
# that is exposed if you remove this. That's not something I've seen before
# but presumably having this here changes the order in which files are imported
# and that ends up mattering.
# todo: figure out what that circular dependency is
from corehq.apps.users.views import mobile
from corehq.apps.hqwebapp.doc_info import get_doc_info, get_doc_info_by_id
from corehq.apps.sms.models import (
    WORKFLOW_REMINDER,
    WORKFLOW_KEYWORD,
    WORKFLOW_BROADCAST,
    WORKFLOW_CALLBACK,
    WORKFLOW_DEFAULT,
    WORKFLOW_FORWARD,
    INCOMING,
    OUTGOING,
    SMSLog,
    MessagingEvent,
    MessagingSubEvent,
    SMS,
)
from corehq.apps.smsforms.models import SQLXFormsSession
from corehq.apps.reminders.models import (SurveyKeyword,
    CaseReminderHandler)
from corehq.apps.reminders.views import (EditStructuredKeywordView,
    EditNormalKeywordView, EditScheduledReminderView)
from couchforms.models import XFormInstance


class MessagesReport(ProjectReport, ProjectReportParametersMixin, GenericTabularReport, DatespanMixin):
    name = ugettext_lazy('SMS Usage')
    slug = 'messages'
    fields = ['corehq.apps.reports.filters.select.GroupFilter',
              'corehq.apps.reports.filters.dates.DatespanFilter']

    special_notice = ugettext_lazy(
        "This report will only show data for users whose phone numbers have "
        "been verified. Phone numbers can be verified from the Settings and "
        "Users tab.")

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_("User Name")),
            DataTablesColumn(_("Number of Messages Received"), sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("Number of Messages Sent"), sort_type=DTSortType.NUMERIC),
            # DataTablesColumn(_("Number of Error Messages Sent"), sort_type=DTSortType.NUMERIC), # TODO
            DataTablesColumn(_("Number of Phone Numbers Used"), sort_type=DTSortType.NUMERIC),
        )

    def get_user_link(self, user):
        user_link_template = '<a href="%(link)s">%(username)s</a>'
        from corehq.apps.users.views.mobile import EditCommCareUserView
        user_link = user_link_template % {
            "link": absolute_reverse(EditCommCareUserView.urlname,
                                     args=[self.domain, user._id]),
            "username": user.username_in_report
        }
        return self.table_cell(user.raw_username, user_link)

    @property
    def rows(self):
        def _row(user):
            # NOTE: this currently counts all messages from the user, whether
            # or not they were from verified numbers
            counts = _sms_count(user, self.datespan.startdate_utc, self.datespan.enddate_utc)
            def _fmt(val):
                return format_datatables_data(val, val)
            return [
                self.get_user_link(user),
                _fmt(counts[OUTGOING]),
                _fmt(counts[INCOMING]),
                _fmt(len(user.get_verified_numbers()))
            ]

        return [
            _row(user) for user in self.get_all_users_by_domain(
                group=self.group_id,
                user_ids=(self.individual,),
                user_filter=tuple(self.user_filter),
                simplified=False
            )
        ]

def _sms_count(user, startdate, enddate, message_type='SMSLog'):
    """
    Returns a dictionary of messages seen for a given type, user, and date
    range of the format:
    {
        I: inbound_count,
        O: outbound_count
    }
    """
    # utilizable if we want to stick it somewhere else
    start_timestamp = json_format_datetime(startdate)
    end_timestamp = json_format_datetime(enddate)
    ret = {}
    for direction in [INCOMING, OUTGOING]:
        results = SMSLog.get_db().view("sms/by_recipient",
            startkey=[user.doc_type, user._id, message_type, direction, start_timestamp],
            endkey=[user.doc_type, user._id, message_type, direction, end_timestamp],
            reduce=True).all()
        ret[direction] = results[0]['value'] if results else 0

    return ret

class BaseCommConnectLogReport(ProjectReport, ProjectReportParametersMixin, GenericTabularReport, DatespanMixin):
    def _fmt(self, val):
        if val is None:
            return format_datatables_data("-", "-")
        else:
            return format_datatables_data(val, val)

    def _fmt_direction(self, direction):
        return self._fmt({
            INCOMING: _('Incoming'),
            OUTGOING: _('Outgoing'),
        }.get(direction, '-'))

    def _fmt_timestamp(self, timestamp):
        return self.table_cell(
            timestamp,
            timestamp.strftime(SERVER_DATETIME_FORMAT),
        )

    def _fmt_contact_link(self, recipient_id, doc_info):
        if doc_info:
            username, contact_type, url = (doc_info.display,
                doc_info.type_display, doc_info.link)
            if doc_info.is_deleted:
                url = None
                username = '%s (%s %s)' % (username, _('Deleted'), _(doc_info.type_display))
        else:
            username, contact_type, url = (None, None, None)
        username = username or "-"
        contact_type = contact_type or _("Unknown")
        if url:
            ret = self.table_cell(username, '<a target="_blank" href="%s">%s</a>' % (url, username))
        else:
            ret = self.table_cell(username, username)
        ret['raw'] = "|||".join([username, contact_type,
            recipient_id or ""])
        return ret

    def get_recipient_info(self, recipient_doc_type, recipient_id, contact_cache):
        if recipient_id in contact_cache:
            return contact_cache[recipient_id]

        doc = None
        if recipient_id not in [None, ""]:
            try:
                if recipient_doc_type.startswith('CommCareCaseGroup'):
                    doc = CommCareCaseGroup.get(recipient_id)
                elif recipient_doc_type.startswith('CommCareCase'):
                    doc = CommCareCase.get(recipient_id)
                elif recipient_doc_type in ('CommCareUser', 'WebUser'):
                    doc = CouchUser.get_by_user_id(recipient_id)
                elif recipient_doc_type.startswith('Group'):
                    doc = Group.get(recipient_id)
            except Exception:
                pass

        if doc:
            doc_info = get_doc_info(doc.to_json(), self.domain)
        else:
            doc_info = None

        contact_cache[recipient_id] = doc_info

        return doc_info

    @property
    def export_table(self):
        result = super(BaseCommConnectLogReport, self).export_table
        table = result[0][1]
        table[0].append(_("Contact Type"))
        table[0].append(_("Contact Id"))
        for row in table[1:]:
            contact_info = row[1].split("|||")
            row[1] = contact_info[0]
            row.append(contact_info[1])
            row.append(contact_info[2])
        return result

"""
Displays all sms for the given domain and date range.

Some projects only want the beginning digits in the phone number and not the entire phone number.
Since this isn't a common request, the decision was made to not have a field which lets you abbreviate
the phone number, but rather a settings parameter.

So, to have this report abbreviate the phone number to only the first four digits for a certain domain, add 
the domain to the list in settings.MESSAGE_LOG_OPTIONS["abbreviated_phone_number_domains"]
"""
class MessageLogReport(BaseCommConnectLogReport):
    name = ugettext_lazy('Message Log')
    slug = 'message_log'

    exportable = True

    def get_message_type_filter(self):
        filtered_types = MessageTypeFilter.get_value(self.request, self.domain)
        if filtered_types:
            filtered_types = set([mt.lower() for mt in filtered_types])
            return lambda message_types: len(filtered_types.intersection(message_types)) > 0
        return lambda message_types: True

    def get_location_filter(self):
        locations = []
        location_id = AsyncLocationFilter.get_value(self.request, self.domain)
        if location_id:
            locations = SQLLocation.objects.get(
                location_id=location_id
            ).get_descendants(
                include_self=True
            ).filter(
                location_type__administrative=False
            ).values_list('location_id', flat=True)

        return locations

    @staticmethod
    def _get_message_types(message):
        relevant_workflows = [
            WORKFLOW_REMINDER,
            WORKFLOW_KEYWORD,
            WORKFLOW_BROADCAST,
            WORKFLOW_CALLBACK,
            WORKFLOW_DEFAULT,
        ]
        types = []
        if message.workflow in relevant_workflows:
            types.append(message.workflow.lower())
        if message.xforms_session_couch_id is not None:
            types.append(MessageTypeFilter.OPTION_SURVEY.lower())
        if not types:
            types.append(MessageTypeFilter.OPTION_OTHER.lower())
        return types

    @property
    def fields(self):
        fields = [DatespanFilter, MessageTypeFilter]
        if self.uses_locations:
            fields.insert(0, AsyncLocationFilter)
        return fields

    @property
    def headers(self):
        header = DataTablesHeader(
            DataTablesColumn(_("Timestamp")),
            DataTablesColumn(_("User Name")),
            DataTablesColumn(_("Phone Number")),
            DataTablesColumn(_("Direction")),
            DataTablesColumn(_("Message")),
            DataTablesColumn(_("Type")),
        )
        header.custom_sort = [[0, 'desc']]
        return header

    @property
    @memoized
    def uses_locations(self):
        return Domain.get_by_name(self.domain).uses_locations

    @property
    def rows(self):
        startdate = json_format_datetime(self.datespan.startdate_utc)
        enddate = json_format_datetime(self.datespan.enddate_utc)
        data = SMSLog.by_domain_date(self.domain, startdate, enddate)
        result = []

        reporting_locations_id = self.get_location_filter() if self.uses_locations else []
        # Retrieve message log options
        message_log_options = getattr(settings, "MESSAGE_LOG_OPTIONS", {})
        abbreviated_phone_number_domains = message_log_options.get("abbreviated_phone_number_domains", [])
        abbreviate_phone_number = (self.domain in abbreviated_phone_number_domains)

        contact_cache = {}
        message_type_filter = self.get_message_type_filter()

        for message in data:
            if message.direction == OUTGOING and not message.processed:
                continue

            message_types = self._get_message_types(message)
            if not message_type_filter(message_types):
                continue

            if reporting_locations_id and message.location_id not in reporting_locations_id:
                continue

            doc_info = self.get_recipient_info(message.couch_recipient_doc_type,
                message.couch_recipient, contact_cache)

            phone_number = message.phone_number
            if abbreviate_phone_number and phone_number is not None:
                phone_number = phone_number[0:7] if phone_number[0:1] == "+" else phone_number[0:6]

            timestamp = ServerTime(message.date).user_time(self.timezone).done()
            result.append([
                self._fmt_timestamp(timestamp),
                self._fmt_contact_link(message.couch_recipient, doc_info),
                self._fmt(phone_number),
                self._fmt_direction(message.direction),
                self._fmt(message.text),
                self._fmt(", ".join(message_types)),
            ])

        return result


class BaseMessagingEventReport(BaseCommConnectLogReport):
    @property
    def export_table(self):
        # Ignore the BaseCommConnectLogReport export
        return super(BaseCommConnectLogReport, self).export_table

    def get_source_display(self, event, display_only=False):
        source = dict(MessagingEvent.SOURCE_CHOICES).get(event.source)
        if event.source in (
            MessagingEvent.SOURCE_OTHER,
            MessagingEvent.SOURCE_UNRECOGNIZED,
            MessagingEvent.SOURCE_FORWARDED,
        ):
            result = _(source)
        else:
            content_type = dict(MessagingEvent.CONTENT_CHOICES).get(event.content_type)
            result = '%s | %s' % (_(source), _(content_type))

        if display_only:
            return result
        else:
            return self._fmt(result)

    def get_status_display(self, event, sms=None):
        """
        event can be a MessagingEvent or MessagingSubEvent
        """
        # If sms without error, short circuit to the sms status display
        if event.status != MessagingEvent.STATUS_ERROR and sms:
            return self.get_sms_status_display(sms)

        # If survey without error, short circuit to the survey status display
        if (isinstance(event, MessagingSubEvent) and
                event.status == MessagingEvent.STATUS_COMPLETED and
                event.xforms_session_id):
            return _(event.xforms_session.status)

        status = event.status
        error_code = event.error_code
        if status == MessagingEvent.STATUS_ERROR and not error_code:
            error_code = MessagingEvent.ERROR_SUBEVENT_ERROR

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

    def get_sms_status_display(self, sms):
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

    def get_keyword_display(self, keyword_id, content_cache):
        if keyword_id in content_cache:
            args = content_cache[keyword_id]
            return self.table_cell(*args)
        try:
            keyword = SurveyKeyword.get(keyword_id)
            if keyword.deleted():
                display = '%s %s' % (keyword.description, _('(Deleted Keyword)'))
                display_text = display
            else:
                urlname = (EditStructuredKeywordView.urlname if keyword.is_structured_sms()
                    else EditNormalKeywordView.urlname)
                display = '<a target="_blank" href="%s">%s</a>' % (
                    reverse(urlname, args=[keyword.domain, keyword_id]),
                    keyword.description,
                )
                display_text = keyword.description
            args = (display_text, display)
        except ResourceNotFound:
            args = ('-', '-')

        content_cache[keyword_id] = args
        return self.table_cell(*args)

    def get_reminder_display(self, handler_id, content_cache):
        if handler_id in content_cache:
            args = content_cache[handler_id]
            return self.table_cell(*args)
        try:
            reminder_definition = CaseReminderHandler.get(handler_id)
            if reminder_definition.deleted():
                display = '%s %s' % (reminder_definition.nickname, _('(Deleted Reminder)'))
                display_text = display
            else:
                urlname = EditScheduledReminderView.urlname
                display = '<a target="_blank" href="%s">%s</a>' % (
                    reverse(urlname, args=[reminder_definition.domain, handler_id]),
                    reminder_definition.nickname,
                )
                display_text = reminder_definition.nickname
            args = (display_text, display)
        except ResourceNotFound:
            args = ('-', '-')

        content_cache[handler_id] = args
        return self.table_cell(*args)

    def get_content_display(self, event, content_cache):
        if event.source == MessagingEvent.SOURCE_KEYWORD and event.source_id:
            return self.get_keyword_display(event.source_id, content_cache)
        elif event.source == MessagingEvent.SOURCE_REMINDER and event.source_id:
            return self.get_reminder_display(event.source_id, content_cache)
        elif event.content_type in (
            MessagingEvent.CONTENT_SMS_SURVEY,
            MessagingEvent.CONTENT_IVR_SURVEY,
        ):
            return ('%s (%s)' % (_(dict(MessagingEvent.CONTENT_CHOICES).get(event.content_type)),
                event.form_name or _('Unknown')))

        content_choices = dict(MessagingEvent.CONTENT_CHOICES)
        return self._fmt(_(content_choices.get(event.content_type, '-')))

    def get_event_detail_link(self, event):
        display_text = _('View Details')
        display = '<a target="_blank" href="/a/%s/reports/message_event_detail/?id=%s">%s</a>' % (
            self.domain,
            event.pk,
            display_text,
        )
        return self.table_cell(display_text, display)

    def get_survey_detail_link(self, subevent):
        form_name = subevent.form_name or _('Unknown')
        if not subevent.xforms_session_id:
            return self._fmt(form_name)
        else:
            display = '<a target="_blank" href="/a/%s/reports/survey_detail/?id=%s">%s</a>' % (
                self.domain,
                subevent.xforms_session_id,
                form_name,
            )
            return self.table_cell(form_name, display)


class MessagingEventsReport(BaseMessagingEventReport):
    name = ugettext_lazy('Past Events')
    slug = 'messaging_events'
    fields = [
        DatespanFilter,
        EventTypeFilter,
    ]

    @property
    def headers(self):
        header = DataTablesHeader(
            DataTablesColumn(_('Date')),
            DataTablesColumn(_('Content')),
            DataTablesColumn(_('Type')),
            DataTablesColumn(_('Recipient')),
            DataTablesColumn(_('Status')),
            DataTablesColumn(_('Detail')),
        )
        header.custom_sort = [[0, 'desc']]
        return header

    def get_filters(self):
        source_filter = []
        content_type_filter = []
        event_type_filter = EventTypeFilter.get_value(self.request, self.domain)

        for source_type, x in MessagingEvent.SOURCE_CHOICES:
            if source_type in event_type_filter:
                if source_type == MessagingEvent.SOURCE_OTHER:
                    source_filter.extend([
                        MessagingEvent.SOURCE_OTHER,
                        MessagingEvent.SOURCE_FORWARDED,
                    ])
                else:
                    source_filter.append(source_type)

        for content_type, x in MessagingEvent.CONTENT_CHOICES:
            if content_type in event_type_filter:
                if content_type == MessagingEvent.CONTENT_SMS_SURVEY:
                    content_type_filter.extend([
                        MessagingEvent.CONTENT_SMS_SURVEY,
                        MessagingEvent.CONTENT_IVR_SURVEY,
                    ])
                else:
                    content_type_filter.append(content_type)

        return (source_filter, content_type_filter)

    @property
    def rows(self):
        source_filter, content_type_filter = self.get_filters()

        # We need to call distinct() on this because it's doing an
        # outer join to sms_messagingsubevent in order to filter on
        # subevent content types.
        data = MessagingEvent.objects.filter(
            Q(domain=self.domain),
            Q(date__gte=self.datespan.startdate_utc),
            Q(date__lte=self.datespan.enddate_utc),
            (Q(source__in=source_filter) |
                Q(content_type__in=content_type_filter) |
                Q(messagingsubevent__content_type__in=content_type_filter)),
        ).distinct()

        result = []
        contact_cache = {}
        content_cache = {}

        for event in data:
            doc_info = self.get_recipient_info(event.get_recipient_doc_type(),
                event.recipient_id, contact_cache)

            timestamp = ServerTime(event.date).user_time(self.timezone).done()
            status = self.get_status_display(event)
            result.append([
                self._fmt_timestamp(timestamp),
                self.get_content_display(event, content_cache),
                self.get_source_display(event),
                (self._fmt(_('Multiple Recipients'))
                    if event.recipient_type == MessagingEvent.RECIPIENT_VARIOUS
                    else self._fmt_contact_link(event.recipient_id, doc_info)),
                self._fmt(status),
                self.get_event_detail_link(event),
            ])

        return result


class MessageEventDetailReport(BaseMessagingEventReport):
    name = ugettext_lazy('Message Event Detail')
    slug = 'message_event_detail'
    description = ugettext_lazy('Displays the detail for a given messaging event.')
    emailable = False
    exportable = False
    hide_filters = True
    report_template_path = "reports/messaging/event_detail.html"

    @classmethod
    def show_in_navigation(cls, *args, **kwargs):
        return False

    @property
    def template_context(self):
        event = self.get_messaging_event()
        date = ServerTime(event.date).user_time(self.timezone).done()
        return {
            'messaging_event_date': date.strftime(SERVER_DATETIME_FORMAT),
            'messaging_event_type': self.get_source_display(event, display_only=True),
        }

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_('Date')),
            DataTablesColumn(_('Recipient')),
            DataTablesColumn(_('Content')),
            DataTablesColumn(_('Phone Number')),
            DataTablesColumn(_('Direction')),
            DataTablesColumn(_('Gateway')),
            DataTablesColumn(_('Status')),
        )

    @memoized
    def get_messaging_event(self):
        messaging_event_id = self.request.GET.get('id', None)

        try:
            messaging_event_id = int(messaging_event_id)
            messaging_event = MessagingEvent.objects.get(pk=messaging_event_id)
        except (TypeError, ValueError, MessagingEvent.DoesNotExist):
            raise Http404

        if messaging_event.domain != self.domain:
            raise Http404

        return messaging_event

    @property
    def rows(self):
        result = []
        contact_cache = {}
        messaging_event = self.get_messaging_event()
        for messaging_subevent in MessagingSubEvent.objects.filter(parent=messaging_event):
            doc_info = self.get_recipient_info(messaging_subevent.get_recipient_doc_type(),
                messaging_subevent.recipient_id, contact_cache)

            if messaging_subevent.content_type in (MessagingEvent.CONTENT_SMS,
                    MessagingEvent.CONTENT_SMS_CALLBACK):
                messages = SMS.objects.filter(messaging_subevent_id=messaging_subevent.pk)
                if len(messages) == 0:
                    timestamp = ServerTime(messaging_subevent.date).user_time(self.timezone).done()
                    status = self.get_status_display(messaging_subevent)
                    result.append([
                        self._fmt_timestamp(timestamp),
                        self._fmt_contact_link(messaging_subevent.recipient_id, doc_info),
                        self._fmt('-'),
                        self._fmt('-'),
                        self._fmt_direction('-'),
                        self._fmt('-'),
                        self._fmt(status),
                    ])
                else:
                    for sms in messages:
                        timestamp = ServerTime(sms.date).user_time(self.timezone).done()
                        status = self.get_status_display(messaging_subevent, sms)
                        result.append([
                            self._fmt_timestamp(timestamp),
                            self._fmt_contact_link(messaging_subevent.recipient_id, doc_info),
                            self._fmt(sms.text),
                            self._fmt(sms.phone_number),
                            self._fmt_direction(sms.direction),
                            self._fmt(sms.backend_api),
                            self._fmt(status),
                        ])
            elif messaging_subevent.content_type in (MessagingEvent.CONTENT_SMS_SURVEY,
                    MessagingEvent.CONTENT_IVR_SURVEY):
                status = self.get_status_display(messaging_subevent)
                xforms_session = messaging_subevent.xforms_session
                timestamp = xforms_session.start_time if xforms_session else messaging_subevent.date
                timestamp = ServerTime(timestamp).user_time(self.timezone).done()
                result.append([
                    self._fmt_timestamp(timestamp),
                    self._fmt_contact_link(messaging_subevent.recipient_id, doc_info),
                    self.get_survey_detail_link(messaging_subevent),
                    self._fmt('-'),
                    self._fmt('-'),
                    self._fmt('-'),
                    self._fmt(status),
                ])
        return result


class SurveyDetailReport(BaseMessagingEventReport):
    name = ugettext_lazy('Survey Detail')
    slug = 'survey_detail'
    description = ugettext_lazy('Displays the detail for a given messaging survey.')
    emailable = False
    exportable = False
    hide_filters = True
    report_template_path = "reports/messaging/survey_detail.html"

    @classmethod
    def show_in_navigation(cls, *args, **kwargs):
        return False

    @property
    def template_context(self):
        return {
            'xforms_session': self.xforms_session,
            'xform_instance': (XFormInstance.get(self.xforms_session.submission_id)
                               if self.xforms_session.submission_id else None),
            'contact': get_doc_info_by_id(self.domain, self.xforms_session.connection_id),
            'start_time': (ServerTime(self.xforms_session.start_time)
                           .user_time(self.timezone).done().strftime(SERVER_DATETIME_FORMAT)),
        }

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_('Date')),
            DataTablesColumn(_('Content')),
            DataTablesColumn(_('Phone Number')),
            DataTablesColumn(_('Direction')),
            DataTablesColumn(_('Gateway')),
            DataTablesColumn(_('Status')),
        )

    @property
    @memoized
    def xforms_session(self):
        xforms_session_id = self.request.GET.get('id', None)

        try:
            xforms_session_id = int(xforms_session_id)
            xforms_session = SQLXFormsSession.objects.get(pk=xforms_session_id)
        except (TypeError, ValueError, SQLXFormsSession.DoesNotExist):
            raise Http404

        if xforms_session.domain != self.domain:
            raise Http404

        return xforms_session

    @property
    def rows(self):
        result = []
        xforms_session = self.xforms_session
        for sms in SMS.objects.filter(xforms_session_couch_id=xforms_session.couch_id):
            timestamp = ServerTime(sms.date).user_time(self.timezone).done()
            status = self.get_sms_status_display(sms)
            result.append([
                self._fmt_timestamp(timestamp),
                self._fmt(sms.text),
                self._fmt(sms.phone_number),
                self._fmt_direction(sms.direction),
                self._fmt(sms.backend_api),
                self._fmt(status),
            ])
        return result
