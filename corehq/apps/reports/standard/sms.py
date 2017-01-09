import cgi
from django.db.models import Q, Count
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseRedirect
from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _
from couchdbkit.resource import ResourceNotFound
from corehq import toggles
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.filters.fixtures import OptionalAsyncLocationFilter
from corehq.apps.reports.standard import DatespanMixin, ProjectReport, ProjectReportParametersMixin
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader, DTSortType
from corehq.apps.sms.filters import MessageTypeFilter, EventTypeFilter, PhoneNumberFilter, EventStatusFilter
from corehq.const import SERVER_DATETIME_FORMAT
from corehq.util.timezones.conversions import ServerTime
from corehq.util.view_utils import absolute_reverse
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.groups.models import Group
from corehq.apps.reports.util import format_datatables_data
from corehq.apps.users.models import CouchUser
from casexml.apps.case.models import CommCareCase
from datetime import datetime
from django.conf import settings
from corehq.apps.hqwebapp.doc_info import (get_doc_info, get_doc_info_by_id,
    get_object_info, DomainMismatchException)
from corehq.apps.sms.models import (
    WORKFLOW_REMINDER,
    WORKFLOW_KEYWORD,
    WORKFLOW_BROADCAST,
    WORKFLOW_CALLBACK,
    WORKFLOW_DEFAULT,
    WORKFLOW_FORWARD,
    WORKFLOW_PERFORMANCE,
    INCOMING,
    OUTGOING,
    MessagingEvent,
    MessagingSubEvent,
    SMS,
    PhoneBlacklist,
    Keyword,
)
from corehq.apps.sms.util import get_backend_name
from corehq.apps.smsforms.models import SQLXFormsSession
from corehq.apps.reminders.models import CaseReminderHandler
from corehq.apps.reminders.views import (
    EditStructuredKeywordView,
    EditNormalKeywordView,
    EditScheduledReminderView
)


class MessagesReport(ProjectReport, ProjectReportParametersMixin, GenericTabularReport, DatespanMixin):
    name = ugettext_noop('SMS Usage')
    slug = 'messages'
    fields = ['corehq.apps.reports.filters.select.GroupFilter',
              'corehq.apps.reports.filters.dates.DatespanFilter']

    special_notice = ugettext_noop(
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


def _sms_count(user, startdate, enddate):
    """
    Returns a dictionary of messages seen for a given user, and date
    range of the format:
    {
        I: inbound_count,
        O: outbound_count
    }
    """
    # utilizable if we want to stick it somewhere else
    direction_count = SMS.objects.filter(
        couch_recipient_doc_type=user.doc_type,
        couch_recipient=user._id,
        date__range=(startdate, enddate),
    ).values('direction').annotate(Count('direction'))
    ret = {INCOMING: 0, OUTGOING: 0}
    ret.update({d['direction']: d['direction__count'] for d in direction_count})
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

    def _fmt_contact_link(self, recipient_id, doc_info, extra_text=None):
        if doc_info:
            username, contact_type, url = (doc_info.display,
                doc_info.type_display, doc_info.link)
            if doc_info.is_deleted:
                url = None
                username = '%s (%s %s)' % (username, _('Deleted'), _(doc_info.type_display))
        else:
            username, contact_type, url = (None, None, None)
            recipient_id = None

        if username and extra_text:
            username = '%s %s' % (username, extra_text)

        username = username or "-"
        contact_type = contact_type or _("Unknown")
        if url:
            ret = self.table_cell(username, '<a target="_blank" href="%s">%s</a>' % (url, username))
        else:
            ret = self.table_cell(username, username)
        ret['raw'] = "|||".join([username, contact_type,
            recipient_id or ""])
        return ret

    def get_orm_recipient_info(self, recipient_type, recipient_id, contact_cache):
        cache_key = "%s-%s" % (recipient_type, recipient_id)
        if cache_key in contact_cache:
            return contact_cache[cache_key]

        obj = None
        try:
            if recipient_type == 'SQLLocation':
                obj = SQLLocation.objects.get(location_id=recipient_id)
        except Exception:
            pass

        if obj:
            obj_info = get_object_info(obj)
        else:
            obj_info = None

        contact_cache[cache_key] = obj_info
        return obj_info

    def get_recipient_info(self, recipient_doc_type, recipient_id, contact_cache):
        if recipient_doc_type in ['SQLLocation']:
            return self.get_orm_recipient_info(recipient_doc_type, recipient_id, contact_cache)

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

        doc_info = None
        if doc:
            try:
                doc_info = get_doc_info(doc.to_json(), self.domain)
            except DomainMismatchException:
                # This can happen, for example, if a WebUser was sent an SMS
                # and then they unsubscribed from the domain. If that's the
                # case, we'll just leave doc_info as None and no contact link
                # will be displayed.
                pass

        contact_cache[recipient_id] = doc_info

        return doc_info

    @property
    def export_table(self):
        result = super(BaseCommConnectLogReport, self).export_table
        table = result[0][1]
        table[0].insert(0, _("Contact Id"))
        table[0].insert(0, _("Contact Type"))
        for row in table[1:]:
            contact_info = row[1].split("|||")
            row[1] = contact_info[0]
            row.insert(0, contact_info[2])
            row.insert(0, contact_info[1])
        return result


class MessageLogReport(BaseCommConnectLogReport):
    """
    Displays all sms for the given domain and date range.

    Some projects only want the beginning digits in the phone number and not the entire phone number.
    Since this isn't a common request, the decision was made to not have a field which lets you abbreviate
    the phone number, but rather a settings parameter.

    So, to have this report abbreviate the phone number to only the first four digits for a certain domain, add
    the domain to the list in settings.MESSAGE_LOG_OPTIONS["abbreviated_phone_number_domains"]
    """
    name = ugettext_noop('Message Log')
    slug = 'message_log'
    ajax_pagination = True

    exportable = True

    def get_message_type_filter(self):
        filtered_types = MessageTypeFilter.get_value(self.request, self.domain)
        if filtered_types:
            filtered_types = set([mt.lower() for mt in filtered_types])
            return lambda message_types: len(filtered_types.intersection(message_types)) > 0
        return lambda message_types: True

    def get_location_filter(self):
        locations_ids = []
        if self.location_id:
            locations_ids = SQLLocation.objects.get(location_id=self.location_id)\
                .get_descendants(include_self=True)\
                .values_list('location_id', flat=True)

        return locations_ids

    @staticmethod
    def _get_message_types(message):
        relevant_workflows = [
            WORKFLOW_REMINDER,
            WORKFLOW_KEYWORD,
            WORKFLOW_BROADCAST,
            WORKFLOW_CALLBACK,
            WORKFLOW_PERFORMANCE,
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
            fields.append(OptionalAsyncLocationFilter)
        return fields

    @property
    def headers(self):
        header = DataTablesHeader(
            DataTablesColumn(_("Timestamp")),
            DataTablesColumn(_("User Name")),
            DataTablesColumn(_("Phone Number")),
            DataTablesColumn(_("Direction")),
            DataTablesColumn(_("Message")),
            DataTablesColumn(_("Type"), sortable=False),
        )
        header.custom_sort = [[0, 'desc']]
        return header

    @property
    @memoized
    def include_metadata(self):
        return toggles.MESSAGE_LOG_METADATA.enabled(self.request.couch_user.username)

    @property
    @memoized
    def uses_locations(self):
        return (toggles.LOCATIONS_IN_REPORTS.enabled(self.domain)
                and Domain.get_by_name(self.domain).uses_locations)

    @property
    @memoized
    def location_id(self):
        if self.uses_locations:
            return OptionalAsyncLocationFilter.get_value(self.request, self.domain)
        return None

    def _get_queryset(self):

        def filter_by_types(data_):
            filtered_types = set(MessageTypeFilter.get_value(self.request, self.domain))
            if not filtered_types:
                return data_

            relevant_workflows = (
                WORKFLOW_REMINDER,
                WORKFLOW_KEYWORD,
                WORKFLOW_BROADCAST,
                WORKFLOW_CALLBACK,
                WORKFLOW_DEFAULT,
                WORKFLOW_PERFORMANCE,
            )
            incl_survey = MessageTypeFilter.OPTION_SURVEY in filtered_types
            incl_other = MessageTypeFilter.OPTION_OTHER in filtered_types
            is_workflow_relevant = Q(workflow__in=relevant_workflows)
            workflow_filter = Q(is_workflow_relevant & Q(workflow__in=filtered_types))
            survey_filter = Q(xforms_session_couch_id__isnull=False)
            other_filter = ~Q(is_workflow_relevant | survey_filter)
            # We can chain ANDs together, but not ORs, so we have to do all the ORs at the same time.
            if incl_survey and incl_other:
                filters = (workflow_filter | survey_filter | other_filter)
            elif incl_survey:
                filters = (workflow_filter | survey_filter)
            elif incl_other:
                filters = (workflow_filter | other_filter)
            else:
                filters = workflow_filter
            return data_.filter(filters)

        def filter_by_location(data):
            if not self.location_id:
                return data
            location_ids = self.get_location_filter()
            # location_ids is a list of strings because SMS.location_id is a CharField, not a foreign key
            return data.filter(location_id__in=location_ids)

        def order_by_col(data_):
            col_fields = ['date', 'couch_recipient', 'phone_number', 'direction', 'text']
            sort_col = self.request_params.get('iSortCol_0')
            if sort_col is not None and sort_col < len(col_fields):
                data_ = data_.order_by(col_fields[sort_col])
                if self.request_params.get('sSortDir_0') == 'desc':
                    data_ = data_.reverse()
            return data_

        queryset = SMS.objects.filter(
            domain=self.domain,
            date__range=(self.datespan.startdate_utc, self.datespan.enddate_utc),
        ).exclude(
            # Exclude outgoing messages that have not yet been processed
            direction=OUTGOING,
            processed=False
        )
        queryset = filter_by_types(queryset)
        queryset = filter_by_location(queryset)
        queryset = order_by_col(queryset)
        return queryset

    def _get_rows(self, paginate=True, contact_info=False, include_log_id=False):
        message_log_options = getattr(settings, "MESSAGE_LOG_OPTIONS", {})
        abbreviated_phone_number_domains = message_log_options.get("abbreviated_phone_number_domains", [])
        abbreviate_phone_number = (self.domain in abbreviated_phone_number_domains)

        contact_cache = {}

        def get_phone_number(phone_number):
            if abbreviate_phone_number and phone_number is not None:
                return phone_number[0:7] if phone_number[0] == "+" else phone_number[0:6]
            return phone_number

        get_direction = lambda d: self._fmt_direction(d)['html']

        def get_timestamp(date_):
            timestamp = ServerTime(date_).user_time(self.timezone).done()
            table_cell = self._fmt_timestamp(timestamp)
            return table_cell['html']

        def get_contact_link(couch_recipient, couch_recipient_doc_type, raw=False):
            doc_info = self.get_recipient_info(couch_recipient_doc_type, couch_recipient, contact_cache)
            table_cell = self._fmt_contact_link(couch_recipient, doc_info)
            return table_cell['raw'] if raw else table_cell['html']

        data = self._get_queryset()
        if paginate and self.pagination:
            data = data[self.pagination.start:self.pagination.start + self.pagination.count]

        for message in data:
            row = [
                get_timestamp(message.date),
                get_contact_link(message.couch_recipient, message.couch_recipient_doc_type, raw=contact_info),
                get_phone_number(message.phone_number),
                get_direction(message.direction),
                message.text,
                ', '.join(self._get_message_types(message)),
            ]
            if include_log_id and self.include_metadata:
                row.append(message.couch_id)
            yield row

    @property
    def rows(self):
        return self._get_rows(paginate=True, contact_info=False)

    @property
    def total_records(self):
        queryset = self._get_queryset()
        return queryset.count()

    @property
    def shared_pagination_GET_params(self):
        start_date = self.datespan.startdate.strftime('%Y-%m-%d')
        end_date = self.datespan.enddate.strftime('%Y-%m-%d')
        return [
            {'name': 'startdate', 'value': start_date},
            {'name': 'enddate', 'value': end_date},
            {'name': 'log_type', 'value': MessageTypeFilter.get_value(self.request, self.domain)},
            {'name': 'location_id', 'value': self.location_id},
        ]

    @property
    def export_rows(self):
        return self._get_rows(paginate=False, contact_info=True, include_log_id=True)

    @property
    def export_table(self):
        result = super(MessageLogReport, self).export_table
        if self.include_metadata:
            table = result[0][1]
            table[0].append(_("Message Log ID"))
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
                xforms_session__end_time__isnull=True
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

    def get_reminder_display(self, handler_id, content_cache):
        if handler_id in content_cache:
            return content_cache[handler_id]
        try:
            reminder_definition = CaseReminderHandler.get(handler_id)
            if reminder_definition.deleted():
                display = '%s %s' % (reminder_definition.nickname, _('(Deleted Reminder)'))
            else:
                urlname = EditScheduledReminderView.urlname
                display = '<a target="_blank" href="%s">%s</a>' % (
                    reverse(urlname, args=[reminder_definition.domain, handler_id]),
                    reminder_definition.nickname,
                )
        except ResourceNotFound:
            display = '-'

        content_cache[handler_id] = display
        return display

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
        return _(content_choices.get(event.content_type, '-'))

    def get_event_detail_link(self, event):
        display_text = _('View Details')
        display = '<a target="_blank" href="/a/%s/reports/message_event_detail/?id=%s">%s</a>' % (
            self.domain,
            event.pk,
            display_text,
        )
        return display

    def get_survey_detail_url(self, subevent):
        return "/a/%s/reports/survey_detail/?id=%s" % (self.domain, subevent.xforms_session_id)

    def get_survey_detail_link(self, subevent):
        form_name = subevent.form_name or _('Unknown')
        if not subevent.xforms_session_id:
            return self._fmt(form_name)
        else:
            display = '<a target="_blank" href="%s">%s</a>' % (
                self.get_survey_detail_url(subevent),
                form_name,
            )
            return self.table_cell(form_name, display)


class MessagingEventsReport(BaseMessagingEventReport):
    name = ugettext_noop('Messaging History')
    slug = 'messaging_events'
    fields = [
        DatespanFilter,
        EventTypeFilter,
        EventStatusFilter,
        PhoneNumberFilter,
    ]
    ajax_pagination = True

    @property
    def headers(self):
        header = DataTablesHeader(
            DataTablesColumn(_('Date')),
            DataTablesColumn(_('Content'), sortable=False),
            DataTablesColumn(_('Type'), sortable=False),
            DataTablesColumn(_('Recipient'), sortable=False),
            DataTablesColumn(_('Status'), sortable=False),
            DataTablesColumn(_('Detail'), sortable=False),
        )
        header.custom_sort = [[0, 'desc']]
        return header

    @property
    @memoized
    def phone_number_filter(self):
        value = PhoneNumberFilter.get_value(self.request, self.domain)
        if isinstance(value, basestring):
            return value.strip()

        return None

    def get_filters(self):
        source_filter = []
        content_type_filter = []
        event_status_filter = None
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

        event_status = EventStatusFilter.get_value(self.request, self.domain)
        if event_status == MessagingEvent.STATUS_ERROR:
            event_status_filter = (
                Q(status=event_status) |
                Q(messagingsubevent__status=event_status) |
                Q(messagingsubevent__sms__error=True)
            )
        elif event_status == MessagingEvent.STATUS_IN_PROGRESS:
            # We need to check for id__isnull=False below because the
            # query we make in this report has to do a left join, and
            # in this particular filter we can only validly check
            # end_time__isnull=True if there actually are
            # subevent and xforms session records
            event_status_filter = (
                Q(status=event_status) |
                Q(messagingsubevent__status=event_status) |
                (Q(messagingsubevent__xforms_session__id__isnull=False) &
                 Q(messagingsubevent__xforms_session__end_time__isnull=True))
            )
        elif event_status == MessagingEvent.STATUS_NOT_COMPLETED:
            event_status_filter = (
                Q(status=event_status) |
                Q(messagingsubevent__status=event_status) |
                (Q(messagingsubevent__xforms_session__end_time__isnull=False) &
                 Q(messagingsubevent__xforms_session__submission_id__isnull=True))
            )

        return source_filter, content_type_filter, event_status_filter

    def _fmt_recipient(self, event, doc_info):
        if event.recipient_type in (
            MessagingEvent.RECIPIENT_VARIOUS,
            MessagingEvent.RECIPIENT_VARIOUS_LOCATIONS,
            MessagingEvent.RECIPIENT_VARIOUS_LOCATIONS_PLUS_DESCENDANTS,
        ):
            return self._fmt(_(dict(MessagingEvent.RECIPIENT_CHOICES)[event.recipient_type]))
        else:
            return self._fmt_contact_link(
                event.recipient_id,
                doc_info,
                extra_text=(_('(including child locations)')
                            if event.recipient_type == MessagingEvent.RECIPIENT_LOCATION_PLUS_DESCENDANTS
                            else None)
            )

    def get_queryset(self):
        source_filter, content_type_filter, event_status_filter = self.get_filters()

        data = MessagingEvent.objects.filter(
            Q(domain=self.domain),
            Q(date__gte=self.datespan.startdate_utc),
            Q(date__lte=self.datespan.enddate_utc),
            (Q(source__in=source_filter) |
                Q(content_type__in=content_type_filter) |
                Q(messagingsubevent__content_type__in=content_type_filter)),
        )

        if event_status_filter:
            data = data.filter(event_status_filter)

        if self.phone_number_filter:
            data = data.filter(messagingsubevent__sms__phone_number__contains=self.phone_number_filter)

        # We need to call distinct() on this because it's doing an
        # outer join to sms_messagingsubevent in order to filter on
        # subevent content types.
        data = data.distinct()
        return data

    @property
    def total_records(self):
        return self.get_queryset().count()

    @property
    def shared_pagination_GET_params(self):
        return [
            {'name': 'startdate', 'value': self.datespan.startdate.strftime('%Y-%m-%d')},
            {'name': 'enddate', 'value': self.datespan.enddate.strftime('%Y-%m-%d')},
            {'name': EventTypeFilter.slug, 'value': EventTypeFilter.get_value(self.request, self.domain)},
            {'name': EventStatusFilter.slug, 'value': EventStatusFilter.get_value(self.request, self.domain)},
            {'name': PhoneNumberFilter.slug, 'value': PhoneNumberFilter.get_value(self.request, self.domain)},
        ]

    @property
    def rows(self):
        contact_cache = {}
        content_cache = {}

        data = self.get_queryset()
        if self.request_params.get('sSortDir_0') == 'asc':
            data = data.order_by('date')
        else:
            data = data.order_by('-date')

        if self.pagination:
            data = data[self.pagination.start:self.pagination.start + self.pagination.count]

        for event in data:
            doc_info = self.get_recipient_info(event.get_recipient_doc_type(),
                event.recipient_id, contact_cache)

            timestamp = ServerTime(event.date).user_time(self.timezone).done()
            status = self.get_status_display(event)
            yield [
                self._fmt_timestamp(timestamp)['html'],
                self.get_content_display(event, content_cache),
                self.get_source_display(event, display_only=True),
                self._fmt_recipient(event, doc_info)['html'],
                status,
                self.get_event_detail_link(event),
            ]


class MessageEventDetailReport(BaseMessagingEventReport):
    name = ugettext_noop('Message Event Detail')
    slug = 'message_event_detail'
    description = ugettext_noop('Displays the detail for a given messaging event.')
    emailable = False
    exportable = False
    hide_filters = True
    report_template_path = "reports/messaging/event_detail.html"

    @classmethod
    def show_in_navigation(cls, *args, **kwargs):
        return False

    @property
    def template_context(self):
        event = self.messaging_event
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

    @property
    @memoized
    def messaging_event(self):
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
    @memoized
    def messaging_subevents(self):
        return MessagingSubEvent.objects.filter(parent=self.messaging_event)

    def _fmt_backend_name(self, sms):
        return self._fmt(get_backend_name(sms.backend_id) or sms.backend_api)

    @property
    def view_response(self):
        subevents = self.messaging_subevents
        if (
            len(subevents) == 1 and
            subevents[0].content_type in (MessagingEvent.CONTENT_SMS_SURVEY,
                                          MessagingEvent.CONTENT_IVR_SURVEY) and
            subevents[0].xforms_session_id and
            subevents[0].status != MessagingEvent.STATUS_ERROR
        ):
            # There's only one survey to report on here - just redirect to the
            # survey detail page
            return HttpResponseRedirect(self.get_survey_detail_url(subevents[0]))

        return super(MessageEventDetailReport, self).view_response

    @property
    def rows(self):
        result = []
        contact_cache = {}
        for messaging_subevent in self.messaging_subevents:
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
                            self._fmt_backend_name(sms),
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
            elif messaging_subevent.content_type == MessagingEvent.CONTENT_EMAIL:
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
        return result


class SurveyDetailReport(BaseMessagingEventReport):
    name = ugettext_noop('Survey Detail')
    slug = 'survey_detail'
    description = ugettext_noop('Displays the detail for a given messaging survey.')
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


class SMSOptOutReport(ProjectReport, ProjectReportParametersMixin, GenericTabularReport):

    name = ugettext_noop("SMS Opt Out Report")
    slug = 'sms_opt_out'
    ajax_pagination = True
    exportable = True
    fields = []

    @property
    def headers(self):
        header = DataTablesHeader(
            DataTablesColumn(_("Phone Number")),
            DataTablesColumn(_("Can Receive SMS")),
            DataTablesColumn(_("Last Opt Out Timestamp")),
            DataTablesColumn(_("Last Opt In Timestamp")),
        )
        return header

    def _get_queryset(self):
        qs = PhoneBlacklist.objects.filter(
            domain=self.domain
        )

        fields = ['phone_number', 'send_sms', 'last_sms_opt_out_timestamp', 'last_sms_opt_in_timestamp']
        sort_col = self.request_params.get('iSortCol_0')
        sort_dir = self.request_params.get('sSortDir_0')

        if isinstance(sort_col, int) and sort_col < len(fields):
            qs = qs.order_by(fields[sort_col])
            if sort_dir == 'desc':
                qs = qs.reverse()

        return qs

    def _get_rows(self, paginate=True):
        qs = self._get_queryset()
        if paginate:
            qs = qs[self.pagination.start:self.pagination.start + self.pagination.count]
        for entry in qs:
            yield [
                self._fmt(entry.phone_number),
                self._fmt_bool(entry.send_sms),
                self._fmt_timestamp(entry.last_sms_opt_out_timestamp),
                self._fmt_timestamp(entry.last_sms_opt_in_timestamp),
            ]

    def _fmt(self, value):
        return value or '-'

    def _fmt_bool(self, value):
        return _("Yes") if value else _("No")

    def _fmt_timestamp(self, timestamp):
        if not isinstance(timestamp, datetime):
            return '-'

        timestamp = ServerTime(timestamp).user_time(self.timezone).done()
        return timestamp.strftime(SERVER_DATETIME_FORMAT)

    @property
    def rows(self):
        return self._get_rows()

    @property
    def total_records(self):
        return self._get_queryset().count()

    @property
    def shared_pagination_GET_params(self):
        return []

    @property
    def export_rows(self):
        return self._get_rows(paginate=False)
