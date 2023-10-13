from collections import namedtuple
from datetime import datetime

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, F, Q
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, gettext_noop

from couchdbkit import ResourceNotFound
from memoized import memoized

from corehq import toggles
from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.data_interfaces.views import CaseGroupCaseManagementView
from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.hqwebapp.doc_info import (
    DomainMismatchException,
    get_doc_info,
    get_doc_info_by_id,
)
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.views import EditLocationView
from corehq.apps.reports.datatables import (
    DataTablesColumn,
    DataTablesHeader,
    DTSortType,
)
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.filters.fixtures import OptionalAsyncLocationFilter
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import (
    DatespanMixin,
    ProjectReport,
    ProjectReportParametersMixin,
)
from corehq.apps.reports.standard.message_event_display import (
    EventStub,
    get_event_display,
    get_sms_status_display,
    get_status_display,
)
from corehq.apps.reports.util import format_datatables_data
from corehq.apps.sms.filters import (
    ErrorCodeFilter,
    EventContentFilter,
    EventStatusFilter,
    EventTypeFilter,
    MessageTypeFilter,
    PhoneNumberOrEmailFilter,
    PhoneNumberReportFilter,
)
from corehq.apps.sms.mixin import apply_leniency
from corehq.apps.sms.models import (
    INCOMING,
    OUTGOING,
    SMS,
    WORKFLOWS_FOR_REPORTS,
    MessagingEvent,
    MessagingSubEvent,
    PhoneBlacklist,
    PhoneNumber,
    Email
)
from corehq.apps.sms.util import get_backend_name
from corehq.apps.smsforms.models import SQLXFormsSession
from corehq.apps.users.dbaccessors import get_user_id_and_doc_type_by_domain
from corehq.apps.users.models import CommCareUser, CouchUser, WebUser
from corehq.apps.users.views import EditWebUserView
from corehq.apps.users.views.mobile import (
    EditCommCareUserView,
    EditGroupMembersView,
)
from corehq.const import SERVER_DATETIME_FORMAT
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.utils import is_commcarecase
from corehq.messaging.scheduling.filters import ScheduleInstanceFilter
from corehq.messaging.scheduling.models import (
    ImmediateBroadcast,
    ScheduledBroadcast,
)
from corehq.messaging.scheduling.scheduling_partitioned.models import (
    AlertScheduleInstance,
    CaseAlertScheduleInstance,
    CaseTimedScheduleInstance,
    TimedScheduleInstance,
)
from corehq.messaging.scheduling.views import (
    EditConditionalAlertView,
    EditScheduleView,
)
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from corehq.util.timezones.conversions import ServerTime, UserTime
from corehq.util.view_utils import absolute_reverse


class MessagesReport(ProjectReport, ProjectReportParametersMixin, GenericTabularReport, DatespanMixin):
    name = gettext_noop('SMS Usage')
    slug = 'messages'
    fields = ['corehq.apps.reports.filters.select.GroupFilter',
              'corehq.apps.reports.filters.dates.DatespanFilter']

    special_notice = gettext_noop(
        "This report will only show data for users whose phone numbers have "
        "been verified. Phone numbers can be verified from the Settings and "
        "Users tab.")
    default_datespan_end_date_to_today = True

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
        user_link_template = '<a href="{link}">{username}</a>'
        user_link = format_html(
            user_link_template,
            link=absolute_reverse(EditCommCareUserView.urlname,
                args=[self.domain, user._id]),
            username=user.username_in_report
        )
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
                _fmt(len(user.get_two_way_numbers()))
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
    contact_index_in_result = 1
    default_datespan_end_date_to_today = True

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
            ret = self.table_cell(username, format_html('<a target="_blank" href="{}">{}</a>', url, username))
        else:
            ret = self.table_cell(username, username)
        ret['raw'] = "|||".join([username, contact_type,
            recipient_id or ""])
        return ret

    def get_recipient_info(self, domain, recipient_doc_type, recipient_id, contact_cache):
        """
        We need to accept domain as an arg here for admin reports that extend this base.
        """

        if recipient_id in contact_cache:
            return contact_cache[recipient_id]

        couch_object = None
        sql_object = None

        if recipient_id and recipient_doc_type:
            try:
                if recipient_doc_type.startswith('CommCareCaseGroup'):
                    couch_object = CommCareCaseGroup.get(recipient_id)
                elif recipient_doc_type.startswith('CommCareCase'):
                    obj = CommCareCase.objects.get_case(recipient_id, domain)
                    if isinstance(obj, CommCareCase):
                        sql_object = obj
                elif recipient_doc_type in ('CommCareUser', 'WebUser'):
                    couch_object = CouchUser.get_by_user_id(recipient_id)
                elif recipient_doc_type.startswith('Group'):
                    couch_object = Group.get(recipient_id)
                elif recipient_doc_type == 'SQLLocation':
                    sql_object = SQLLocation.objects.get(location_id=recipient_id)
            except (ResourceNotFound, CaseNotFound, ObjectDoesNotExist):
                pass

        doc, doc_info = None, None
        if couch_object:
            doc = couch_object.to_json()
        elif sql_object:
            doc = sql_object

        if doc:
            try:
                doc_info = get_doc_info(doc, domain)
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
        table = list(table)
        table[0].insert(0, _("Contact Id"))
        table[0].insert(0, _("Contact Type"))
        for row in table[1:]:
            contact_info = row[self.contact_index_in_result].split("|||")
            row[self.contact_index_in_result] = contact_info[0]
            row.insert(0, contact_info[2])
            row.insert(0, contact_info[1])
        result[0][1] = table
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
    name = gettext_noop('Message Log')
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
        types = []
        if message.workflow in WORKFLOWS_FOR_REPORTS:
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
        headers = DataTablesHeader(*[header for header in [
            DataTablesColumn(_("Timestamp")),
            DataTablesColumn(_("User Name")),
            DataTablesColumn(_("Phone Number")),
            DataTablesColumn(_("Direction")),
            DataTablesColumn(_("Message")),
            DataTablesColumn(_("Status")) if self.show_v2 else Ellipsis,
            DataTablesColumn(_("Event"), sortable=False) if self.show_v2 else Ellipsis,
            DataTablesColumn(_("Type"), sortable=False),
        ] if header != Ellipsis])
        headers.custom_sort = [[0, 'desc']]
        return headers

    @cached_property
    def show_v2(self):
        return toggles.SMS_LOG_CHANGES.enabled_for_request(self.request)

    @property
    @memoized
    def include_metadata(self):
        return toggles.MESSAGE_LOG_METADATA.enabled(self.request.couch_user.username)

    @property
    @memoized
    def uses_locations(self):
        return Domain.get_by_name(self.domain).uses_locations

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

            incl_survey = MessageTypeFilter.OPTION_SURVEY in filtered_types
            incl_other = MessageTypeFilter.OPTION_OTHER in filtered_types
            is_workflow_relevant = Q(workflow__in=WORKFLOWS_FOR_REPORTS)
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
            data_ = data_.order_by(self._sort_column)
            if self._sort_descending:
                data_ = data_.reverse()
            return data_

        queryset = SMS.objects.filter(
            domain=self.domain,
            date__range=(self.datespan.startdate_utc, self.datespan.enddate_utc),
        )
        if self.show_v2:
            queryset = queryset.exclude(
                direction=OUTGOING,
                processed=False,
                error=False,  # Don't exclude errored messages
            )
        else:
            # Exclude outgoing messages that have not yet been processed
            # Note that this also excludes errored messages
            queryset = queryset.exclude(
                direction=OUTGOING,
                processed=False,
            )
        queryset = filter_by_types(queryset)
        queryset = filter_by_location(queryset)
        queryset = order_by_col(queryset)
        if self.show_v2:
            return queryset.annotate(
                event_source=F("messaging_subevent__parent__source"),
                event_source_id=F("messaging_subevent__parent__source_id"),
                event_content_type=F("messaging_subevent__parent__content_type"),
                event_form_name=F("messaging_subevent__parent__form_name"),
            )
        return queryset

    @property
    def _sort_column(self):
        col_fields = ['date', 'couch_recipient', 'phone_number', 'direction', 'text']
        sort_col = self.request_params.get('iSortCol_0')
        if sort_col is None or sort_col < 0 or sort_col >= len(col_fields):
            sort_col = 0
        return col_fields[sort_col]

    @property
    def _sort_descending(self):
        return self.request_params.get('sSortDir_0') == 'desc'

    def _get_rows(self, paginate=True, contact_info=False, include_log_id=False):
        message_log_options = getattr(settings, "MESSAGE_LOG_OPTIONS", {})
        abbreviated_phone_number_domains = message_log_options.get("abbreviated_phone_number_domains", [])
        abbreviate_phone_number = (self.domain in abbreviated_phone_number_domains)

        contact_cache = {}

        def get_phone_number(phone_number):
            if abbreviate_phone_number and phone_number is not None:
                return phone_number[0:7] if phone_number[0] == "+" else phone_number[0:6]
            return phone_number

        def get_direction(d):
            return self._fmt_direction(d)['html']

        def get_timestamp(date_):
            timestamp = ServerTime(date_).user_time(self.timezone).done()
            table_cell = self._fmt_timestamp(timestamp)
            return table_cell['html']

        def get_contact_link(couch_recipient, couch_recipient_doc_type, raw=False):
            doc_info = self.get_recipient_info(self.domain, couch_recipient_doc_type, couch_recipient,
                contact_cache)
            table_cell = self._fmt_contact_link(couch_recipient, doc_info)
            return table_cell['raw'] if raw else table_cell['html']

        content_cache = {}
        messages = self._get_data(paginate)
        events = self._get_events_by_xforms_session(messages) if self.show_v2 else {}
        for message in messages:
            yield [val for val in [
                get_timestamp(message.date),
                get_contact_link(message.couch_recipient, message.couch_recipient_doc_type, raw=contact_info),
                get_phone_number(message.phone_number),
                get_direction(message.direction),
                message.text,
                get_sms_status_display(message) if self.show_v2 else Ellipsis,
                self._get_event_display(message, events, content_cache) if self.show_v2 else Ellipsis,
                ', '.join(self._get_message_types(message)),
                message.couch_id if include_log_id and self.include_metadata else Ellipsis,
            ] if val != Ellipsis]

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
            table = list(result[0][1])
            table[0].append(_("Message Log ID"))
            result[0][1] = table

        return result

    def _get_data(self, paginate):
        """Returns the full set of data that will be shown to the user"""
        queryset = self._get_queryset()

        if paginate and self.pagination:
            queryset = queryset[self.pagination.start:self.pagination.start + self.pagination.count]
        return list(queryset)

    def _get_events_by_xforms_session(self, messages):
        session_ids = [
            m.xforms_session_couch_id for m in messages
            if m.xforms_session_couch_id and not m.messaging_subevent_id
        ]
        subevents = (MessagingSubEvent.objects
                     .filter(domain=self.domain,
                             xforms_session__couch_id__in=session_ids)
                     .values_list(
                         'xforms_session__couch_id',
                         'parent__source',
                         'parent__source_id',
                         'parent__content_type',
                         'parent__form_name',
                     ))
        return {session_id: EventStub(source, source_id, content_type, form_name)
                for session_id, source, source_id, content_type, form_name in subevents}

    def _get_event_display(self, message, events, content_cache):
        """Extract event data from a message annotated via _get_data optimizations"""
        event = None
        if message.messaging_subevent:
            event = EventStub(
                message.event_source,
                message.event_source_id,
                message.event_content_type,
                message.event_form_name,
            )
        elif message.xforms_session_couch_id:
            event = events.get(message.xforms_session_couch_id, None)
        if event:
            return get_event_display(self.domain, event, content_cache)
        return "-"


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

    def get_event_detail_link(self, event):
        display_text = _('View Details')
        display = format_html(
            '<a target="_blank" href="/a/{}/reports/message_event_detail/?id={}">{}</a>',
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
            display = format_html(
                '<a target="_blank" href="{}">{}</a>',
                self.get_survey_detail_url(subevent),
                form_name,
            )
            return self.table_cell(form_name, display)


class MessagingEventsReport(BaseMessagingEventReport):
    name = gettext_noop('Messaging History')
    slug = 'messaging_events'
    fields = [
        DatespanFilter,
        EventTypeFilter,
        EventContentFilter,
        EventStatusFilter,
        ErrorCodeFilter,
        PhoneNumberOrEmailFilter,
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
    def phone_number_or_email_filter(self):
        value = PhoneNumberOrEmailFilter.get_value(self.request, self.domain)
        if isinstance(value, str):
            return value.strip()

        return None

    def get_filters(self):
        source_filter = []
        content_type_filter = []
        error_code_filter = ErrorCodeFilter.get_value(self.request, self.domain)
        event_status_filter = None
        event_type_filter = EventTypeFilter.get_value(self.request, self.domain)

        for source_type, x in MessagingEvent.SOURCE_CHOICES:
            if source_type in event_type_filter:
                if source_type == MessagingEvent.SOURCE_OTHER:
                    source_filter.extend([
                        MessagingEvent.SOURCE_OTHER,
                        MessagingEvent.SOURCE_FORWARDED,
                    ])
                elif source_type == MessagingEvent.SOURCE_BROADCAST:
                    source_filter.extend([
                        MessagingEvent.SOURCE_BROADCAST,
                        MessagingEvent.SOURCE_SCHEDULED_BROADCAST,
                        MessagingEvent.SOURCE_IMMEDIATE_BROADCAST,
                    ])
                elif source_type == MessagingEvent.SOURCE_REMINDER:
                    source_filter.extend([
                        MessagingEvent.SOURCE_REMINDER,
                        MessagingEvent.SOURCE_CASE_RULE,
                    ])
                else:
                    source_filter.append(source_type)

        content_types = EventContentFilter.get_value(self.request, self.domain)

        for content_type, x in MessagingEvent.CONTENT_CHOICES:
            if content_type in content_types:
                if content_type == MessagingEvent.CONTENT_SMS_SURVEY:
                    content_type_filter.extend([
                        MessagingEvent.CONTENT_SMS_SURVEY,
                        MessagingEvent.CONTENT_IVR_SURVEY,
                    ])
                if content_type == MessagingEvent.CONTENT_SMS:
                    content_type_filter.extend([
                        MessagingEvent.CONTENT_SMS,
                        MessagingEvent.CONTENT_PHONE_VERIFICATION,
                        MessagingEvent.CONTENT_ADHOC_SMS,
                        MessagingEvent.CONTENT_API_SMS,
                        MessagingEvent.CONTENT_CHAT_SMS
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
            # session_is_open=True if there actually are
            # subevent and xforms session records
            event_status_filter = (
                Q(status=event_status) |
                Q(messagingsubevent__status=event_status) |
                (Q(messagingsubevent__xforms_session__id__isnull=False) &
                 Q(messagingsubevent__xforms_session__session_is_open=True))
            )
        elif event_status == MessagingEvent.STATUS_NOT_COMPLETED:
            event_status_filter = (
                Q(status=event_status) |
                Q(messagingsubevent__status=event_status) |
                (Q(messagingsubevent__xforms_session__session_is_open=False) &
                 Q(messagingsubevent__xforms_session__submission_id__isnull=True))
            )
        elif event_status == MessagingEvent.STATUS_EMAIL_DELIVERED:
            event_status_filter = (
                Q(status=event_status) |
                Q(messagingsubevent__status=event_status)
            )

        return source_filter, content_type_filter, event_status_filter, error_code_filter

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
        source_filter, content_type_filter, event_status_filter, error_code_filter = self.get_filters()

        data = MessagingEvent.objects.filter(
            Q(domain=self.domain),
            Q(date__gte=self.datespan.startdate_utc),
            Q(date__lte=self.datespan.enddate_utc),
            Q(source__in=source_filter),
        )
        if error_code_filter:
            data = data.filter(
                Q(error_code__in=error_code_filter)
                | Q(messagingsubevent__error_code__in=error_code_filter)
            )

        if content_type_filter:
            data = data.filter(
                (Q(content_type__in=content_type_filter) |
                 Q(messagingsubevent__content_type__in=content_type_filter))
            )

        if event_status_filter:
            data = data.filter(event_status_filter)

        if self.phone_number_or_email_filter:
            phone_qs = data.filter(
                messagingsubevent__sms__phone_number__contains=self.phone_number_or_email_filter)
            email_qs = data.filter(
                messagingsubevent__email__recipient_address__icontains=self.phone_number_or_email_filter)
            data = (email_qs | phone_qs) if self.phone_number_or_email_filter.isdigit() else email_qs

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
            {'name': EventContentFilter.slug, 'value': EventContentFilter.get_value(self.request, self.domain)},
            {'name': EventStatusFilter.slug, 'value': EventStatusFilter.get_value(self.request, self.domain)},
            {'name': ErrorCodeFilter.slug, 'value': ErrorCodeFilter.get_value(self.request, self.domain)},
            {'name': PhoneNumberOrEmailFilter.slug,
             'value': PhoneNumberOrEmailFilter.get_value(self.request, self.domain)},
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
            doc_info = self.get_recipient_info(self.domain, event.get_recipient_doc_type(),
                event.recipient_id, contact_cache)

            timestamp = ServerTime(event.date).user_time(self.timezone).done()
            status = get_status_display(event)
            yield [
                self._fmt_timestamp(timestamp)['html'],
                get_event_display(self.domain, event, content_cache),
                self.get_source_display(event, display_only=True),
                self._fmt_recipient(event, doc_info)['html'],
                status,
                self.get_event_detail_link(event),
            ]


class MessageEventDetailReport(BaseMessagingEventReport):
    name = gettext_noop('Message Event Detail')
    slug = 'message_event_detail'
    description = gettext_noop('Displays the detail for a given messaging event.')
    emailable = False
    exportable = False
    hide_filters = True
    report_template_path = "reports/messaging/event_detail.html"
    parent_report_class = MessagingEventsReport

    @classmethod
    def show_in_navigation(cls, *args, **kwargs):
        return False

    @property
    def template_context(self):
        context = super().template_context
        event = self.messaging_event
        date = ServerTime(event.date).user_time(self.timezone).done()
        context.update({
            'messaging_event_date': date.strftime(SERVER_DATETIME_FORMAT),
            'messaging_event_type': self.get_source_display(event, display_only=True),
        })
        return context

    @property
    def headers(self):
        EMAIL_ADDRRESS = _('Email Address')
        PHONE_NUMBER = _('Phone Number')
        if self.messaging_event and self.messaging_event.content_type == MessagingEvent.CONTENT_EMAIL:
            contact_column = EMAIL_ADDRRESS
        else:
            contact_column = PHONE_NUMBER
        return DataTablesHeader(
            DataTablesColumn(_('Date')),
            DataTablesColumn(_('Recipient')),
            DataTablesColumn(_('Content')),
            DataTablesColumn(contact_column),
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
            doc_info = self.get_recipient_info(self.domain, messaging_subevent.get_recipient_doc_type(),
                messaging_subevent.recipient_id, contact_cache)

            if messaging_subevent.content_type in (MessagingEvent.CONTENT_SMS,
                    MessagingEvent.CONTENT_SMS_CALLBACK):
                messages = SMS.objects.filter(messaging_subevent_id=messaging_subevent.pk)
                if len(messages) == 0:
                    timestamp = ServerTime(messaging_subevent.date).user_time(self.timezone).done()
                    status = get_status_display(messaging_subevent)
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
                        status = get_status_display(messaging_subevent, sms)
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
                status = get_status_display(messaging_subevent)
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
                status = get_status_display(messaging_subevent)
                content = '-'
                recipient_address = '-'
                try:
                    email = Email.objects.get(messaging_subevent=messaging_subevent.pk)
                    content = email.body
                    recipient_address = email.recipient_address
                except Email.DoesNotExist:
                    pass
                result.append([
                    self._fmt_timestamp(timestamp),
                    self._fmt_contact_link(messaging_subevent.recipient_id, doc_info),
                    self._fmt(content),
                    self._fmt(recipient_address),
                    self._fmt_direction(OUTGOING),
                    self._fmt(_('Email')),
                    self._fmt(status),
                ])
        return result


class SurveyDetailReport(BaseMessagingEventReport):
    name = gettext_noop('Survey Detail')
    slug = 'survey_detail'
    description = gettext_noop('Displays the detail for a given messaging survey.')
    emailable = False
    exportable = False
    hide_filters = True
    report_template_path = "reports/messaging/survey_detail.html"
    parent_report_class = MessagingEventsReport

    @classmethod
    def show_in_navigation(cls, *args, **kwargs):
        return False

    @property
    def template_context(self):
        context = super().template_context
        context.update({
            'xforms_session': self.xforms_session,
            'contact': get_doc_info_by_id(self.domain, self.xforms_session.connection_id),
            'start_time': (ServerTime(self.xforms_session.start_time)
                           .user_time(self.timezone).done().strftime(SERVER_DATETIME_FORMAT)),
        })
        return context

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
            status = get_sms_status_display(sms)
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

    name = gettext_noop("SMS Opt Out Report")
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


class PhoneNumberReport(BaseCommConnectLogReport):
    name = gettext_noop("Phone Number Report")
    slug = 'phone_number_report'
    ajax_pagination = True
    exportable = True
    fields = [
        PhoneNumberReportFilter
    ]
    contact_index_in_result = 0

    @property
    def headers(self):
        header = DataTablesHeader(
            DataTablesColumn(_("Contact"), sortable=False),
            DataTablesColumn(_("Phone Number"), sortable=False),
            DataTablesColumn(_("Status"), sortable=False),
            DataTablesColumn(_("Is Two-Way"), sortable=False),
        )
        return header

    @property
    @memoized
    def _filter(self):
        return PhoneNumberReportFilter.get_value(self.request, self.domain)

    @property
    def filter_type(self):
        return self._filter['filter_type']

    @property
    @memoized
    def phone_number_filter(self):
        value = self._filter['phone_number_filter']
        if isinstance(value, str):
            return apply_leniency(value.strip())

        return None

    @property
    def contact_type(self):
        return self._filter['contact_type']

    @property
    def selected_group(self):
        return self._filter['selected_group']

    @property
    @memoized
    def user_ids_in_selected_group(self):
        return Group.get(self.selected_group).users

    @property
    def has_phone_number(self):
        return self._filter['has_phone_number']

    @property
    def verification_status(self):
        return self._filter['verification_status']

    @property
    def _show_users_without_phone_numbers(self):
        return (
            self.filter_type == 'contact' and
            self.contact_type == 'users' and
            self.has_phone_number != 'has_phone_number'
        )

    @property
    def _show_cases(self):
        return self.contact_type == 'cases'

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return domain and toggles.PHONE_NUMBERS_REPORT.enabled(domain)

    def _fmt_owner(self, domain, owner_doc_type, owner_id, owner_cache, link_user=True):
        doc_info = self.get_recipient_info(domain, owner_doc_type, owner_id, owner_cache)
        table_cell = self._fmt_contact_link(owner_id, doc_info)
        return table_cell['html'] if link_user else table_cell['raw']

    def _fmt_status(self, number):
        if number.verified:
            return "Verified"
        elif number.pending_verification:
            return "Verification Pending"
        elif (
                not (number.is_two_way or number.pending_verification) and
                PhoneNumber.get_reserved_number(number.phone_number)
             ):
            return "Already In Use"
        return "Not Verified"

    def _fmt_row(self, number, owner_cache, link_user):
        if isinstance(number, PhoneNumber):
            return [
                self._fmt_owner(number.domain, number.owner_doc_type, number.owner_id, owner_cache, link_user),
                number.phone_number,
                self._fmt_status(number),
                "Yes" if number.is_two_way else "No",
            ]

        return [
            self._fmt_owner(number.domain, number.owner_doc_type, number.owner_id, owner_cache, link_user),
            '---',
            '---',
            '---',
        ]

    def _get_rows(self, paginate=True, link_user=True):
        owner_cache = {}
        if self._show_users_without_phone_numbers:
            data = self._get_users_without_phone_numbers()
        else:
            data = self._get_queryset()

        if paginate and self.pagination:
            data = data[self.pagination.start:self.pagination.start + self.pagination.count]

        for number in data:
            yield self._fmt_row(number, owner_cache, link_user)

    def _get_queryset(self):
        query = PhoneNumber.objects.filter(domain=self.domain)

        if self.filter_type == 'phone_number':
            if self.phone_number_filter:
                query = query.filter(phone_number=self.phone_number_filter)
        elif self.filter_type == 'contact':
            if self._show_cases:
                query = query.filter(owner_doc_type='CommCareCase')
            else:
                query = query.filter(owner_doc_type__in=['CommCareUser', 'WebUser'])
                if self.selected_group:
                    query = query.filter(owner_id__in=self.user_ids_in_selected_group)

            if self.verification_status == 'not_verified':
                query = query.filter(pending_verification=False, verified=False)
            elif self.verification_status == 'verification_pending':
                query = query.filter(pending_verification=True)
            elif self.verification_status == 'verified':
                query = query.filter(verified=True)

        return query.order_by('phone_number', 'couch_id')

    @memoized
    def _get_users_without_phone_numbers(self):
        query = (
            PhoneNumber.objects.filter(domain=self.domain).filter(owner_doc_type__in=['CommCareUser', 'WebUser'])
        )

        if self.selected_group:
            users_by_id = {
                id: {'_id': id, 'doc_type': 'CommCareUser'}
                for id in self.user_ids_in_selected_group
            }
            query.filter(owner_id__in=list(users_by_id))
        else:
            users_by_id = {u['id']: u for u in get_user_id_and_doc_type_by_domain(self.domain)}

        user_ids_with_phone_numbers = set(query.values_list('owner_id', flat=True).distinct())
        user_ids = set(users_by_id) - user_ids_with_phone_numbers
        user_types_with_id = sorted([(id, users_by_id[id]['doc_type']) for id in user_ids])

        FakePhoneNumber = namedtuple('FakePhoneNumber', ['domain', 'owner_id', 'owner_doc_type'])
        return [FakePhoneNumber(self.domain, id, type) for id, type in user_types_with_id]

    @property
    def shared_pagination_GET_params(self):
        return [
            {'name': 'filter_type', 'value': self.filter_type},
            {'name': 'phone_number_filter', 'value': self.phone_number_filter},
            {'name': 'contact_type', 'value': self.contact_type},
            {'name': 'selected_group', 'value': self.selected_group},
            {'name': 'has_phone_number', 'value': self.has_phone_number},
            {'name': 'verification_status', 'value': self.verification_status},
        ]

    @property
    def rows(self):
        return self._get_rows()

    @property
    def total_records(self):
        if self._show_users_without_phone_numbers:
            return len(self._get_users_without_phone_numbers())
        return self._get_queryset().count()

    @property
    def export_rows(self):
        return self._get_rows(paginate=False, link_user=False)


class ScheduleInstanceReport(ProjectReport, ProjectReportParametersMixin, GenericTabularReport):
    name = gettext_lazy('Scheduled Messaging Events')
    slug = 'scheduled_messaging_events'
    fields = [
        ScheduleInstanceFilter,
    ]
    ajax_pagination = True
    sortable = False

    @property
    def max_pages_reached(self):
        # This means that we don't allow going past page 1000 when viewing
        # the max per page (100), because it gets computationally harder as
        # the pages go up to produce the right page of results.
        return self.pagination.start >= 100000

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_("Next Event Due")),
            DataTablesColumn(_("Scheduling Configuration")),
            DataTablesColumn(_("Recipient")),
            DataTablesColumn(_("Triggering Case")),
            DataTablesColumn(_("Attempt Number"))
        )

    @property
    def total_records(self):
        return sum(qs.count() for qs in self.get_querysets())

    @cached_property
    def show_active_instances(self):
        """
        The `active` parameter is only used for debugging.

        To use it, just pass active=false into the URL and the report will then only show
        inactive schedule instances.

        This shouldn't be made part of the user-facing filters because an inactive schedule
        instance might show a next event due timestamp that looks confusing. For example,
        for a one-time reminder that sends today at 9am, after it sends it will show as inactive and
        have a next event due timestamp for tomorrow at 9am because it has moved past the last event
        in the schedule and that's what deactivated it. That's normal behavior but would look
        confusing to a user.

        This can be a useful tool for developers when debugging.
        """
        return (self.configuration_filter_value['active'] or '').lower() != 'false'

    @cached_property
    def case_id(self):
        """
        The `case_id` parameter is only used for debugging.

        To use it, just pass case_id=... into the URL and the report will then only show
        case schedule instances that were triggered for that case.
        """
        return self.configuration_filter_value.get('case_id')

    @cached_property
    def configuration_filter_value(self):
        return ScheduleInstanceFilter.get_value(self.request, self.domain)

    @cached_property
    def configuration_type(self):
        return self.configuration_filter_value['configuration_type']

    @cached_property
    def rule_id(self):
        return self.configuration_filter_value['rule_id']

    @cached_property
    def date_selector_type(self):
        return self.configuration_filter_value['date_selector_type']

    @cached_property
    def next_event_due_after(self):
        return self.configuration_filter_value['next_event_due_after']

    @cached_property
    def next_event_due_after_timestamp(self):
        if self.date_selector_type != ScheduleInstanceFilter.SHOW_EVENTS_AFTER_DATE:
            return None

        try:
            timestamp = datetime.strptime(self.next_event_due_after, '%Y-%m-%d')
        except (TypeError, ValueError):
            return None

        return UserTime(timestamp, self.timezone).server_time().done().replace(tzinfo=None)

    def get_utc_timestamp_display(self, timestamp):
        return ServerTime(timestamp).user_time(self.timezone).done().strftime('%Y-%m-%d %H:%M:%S')

    def get_link_display(self, href, text):
        return format_html('<a target="_blank" href="{}">{}</a>', href, text)

    def get_case_display(self, case):
        from corehq.apps.reports.standard.cases.case_data import CaseDataView

        return self.get_link_display(
            reverse(CaseDataView.urlname, args=[self.domain, case.case_id]),
            case.name or '-'
        )

    @memoized
    def get_rule_display(self, rule_id):
        try:
            rule = AutomaticUpdateRule.objects.get(domain=self.domain, pk=rule_id,
                workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING)
        except AutomaticUpdateRule.DoesNotExist:
            return '-'

        if rule.deleted:
            return _("(Deleted Conditional Alert)")
        else:
            return self.get_link_display(
                reverse(EditConditionalAlertView.urlname, args=[self.domain, rule_id]),
                rule.name,
            )

    def get_broadcast_display(self, schedule_instance):
        if isinstance(schedule_instance, AlertScheduleInstance):
            cls = ImmediateBroadcast
            schedule_id = schedule_instance.alert_schedule_id
            broadcast_type = EditScheduleView.IMMEDIATE_BROADCAST
        elif isinstance(schedule_instance, TimedScheduleInstance):
            cls = ScheduledBroadcast
            schedule_id = schedule_instance.timed_schedule_id
            broadcast_type = EditScheduleView.SCHEDULED_BROADCAST
        else:
            raise TypeError("Expected AlertScheduleInstance or TimedScheduleInstance")

        try:
            broadcast = cls.objects.get(domain=self.domain, schedule_id=schedule_id)
        except cls.DoesNotExist:
            return '-'

        if broadcast.deleted:
            return _("(Deleted Broadcast)")
        else:
            return self.get_link_display(
                reverse(EditScheduleView.urlname, args=[self.domain, broadcast_type, broadcast.pk]),
                broadcast.name,
            )

    def get_recipient_display(self, recipient):
        if recipient is None:
            return _("(no recipient)")
        elif isinstance(recipient, (list, tuple)):
            # There should never be lists of lists in recipient, so this should
            # always be a list of objects
            return ", ".join([self.get_recipient_display(r) for r in recipient])
        elif is_commcarecase(recipient):
            return self.get_case_display(recipient)
        elif isinstance(recipient, CommCareUser):
            return self.get_link_display(
                reverse(EditCommCareUserView.urlname, args=[self.domain, recipient.get_id]),
                recipient.username
            )
        elif isinstance(recipient, WebUser):
            return self.get_link_display(
                reverse(EditWebUserView.urlname, args=[self.domain, recipient.get_id]),
                recipient.username
            )
        elif isinstance(recipient, Group):
            return self.get_link_display(
                reverse(EditGroupMembersView.urlname, args=[self.domain, recipient.get_id]),
                recipient.name
            )
        elif isinstance(recipient, CommCareCaseGroup):
            return self.get_link_display(
                reverse(CaseGroupCaseManagementView.urlname, args=[self.domain, recipient.get_id]),
                recipient.name
            )
        elif isinstance(recipient, SQLLocation):
            return self.get_link_display(
                reverse(EditLocationView.urlname, args=[self.domain, recipient.location_id]),
                recipient.name
            )
        else:
            return _("(unknown)")

    def get_querysets(self):
        if self.configuration_type == ScheduleInstanceFilter.TYPE_CONDITIONAL_ALERT:
            classes = (CaseAlertScheduleInstance, CaseTimedScheduleInstance)
        else:
            classes = (AlertScheduleInstance, TimedScheduleInstance)

        for db_alias in get_db_aliases_for_partitioned_query():
            for cls in classes:
                qs = cls.objects.using(db_alias).filter(
                    domain=self.domain,
                    active=self.show_active_instances,
                ).order_by('next_event_due', 'schedule_instance_id')

                if self.next_event_due_after_timestamp:
                    qs = qs.filter(next_event_due__gte=self.next_event_due_after_timestamp)

                if self.configuration_type == ScheduleInstanceFilter.TYPE_CONDITIONAL_ALERT:
                    if self.rule_id:
                        qs = qs.filter(rule_id=self.rule_id)

                    if self.case_id:
                        qs = qs.filter(case_id=self.case_id)

                yield qs

    def get_current_page_records(self):
        result = []

        for qs in self.get_querysets():
            result.extend(qs[:self.pagination.start + self.pagination.count])

        result.sort(key=lambda record: (record.next_event_due, record.schedule_instance_id))

        return result[self.pagination.start:self.pagination.start + self.pagination.count]

    def get_schedule_instance_display(self, schedule_instance):
        if isinstance(schedule_instance, (AlertScheduleInstance, TimedScheduleInstance)):
            return [
                self.get_utc_timestamp_display(schedule_instance.next_event_due),
                self.get_broadcast_display(schedule_instance),
                self.get_recipient_display(schedule_instance.recipient),
                '-',
                schedule_instance.attempts + 1
            ]
        elif isinstance(schedule_instance, (CaseAlertScheduleInstance, CaseTimedScheduleInstance)):
            return [
                self.get_utc_timestamp_display(schedule_instance.next_event_due),
                self.get_rule_display(schedule_instance.rule_id),
                self.get_recipient_display(schedule_instance.recipient),
                self.get_case_display(schedule_instance.case) if schedule_instance.case else '-',
                schedule_instance.attempts + 1
            ]
        else:
            raise TypeError("Unexpected type: %s" % type(schedule_instance))

    @property
    def rows(self):
        if self.max_pages_reached:
            return [[
                _("You have requested a page number which is too high to process. "
                  "Please update the filter criteria above to reduce the number "
                  "of pages in the report."),
                "", "", "", "",
            ]]

        return [
            self.get_schedule_instance_display(schedule_instance)
            for schedule_instance in self.get_current_page_records()
        ]

    @property
    def shared_pagination_GET_params(self):
        result = [
            {'name': 'date_selector_type', 'value': self.date_selector_type},
            {'name': 'next_event_due_after', 'value': self.next_event_due_after},
            {'name': 'configuration_type', 'value': self.configuration_type},
            {'name': 'rule_id', 'value': self.rule_id},
        ]

        if not self.show_active_instances:
            result.append({'name': 'active', 'value': 'false'})

        if self.case_id:
            result.append({'name': 'case_id', 'value': self.case_id})

        return result
