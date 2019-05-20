from __future__ import absolute_import
from __future__ import unicode_literals

from dateutil.rrule import rrule, DAILY, MO, TU, WE, TH, FR, SA
from sqlagg.columns import SimpleColumn
from sqlagg.filters import EQ
from sqlagg.sorting import OrderBy
from django.db.models.aggregates import Count

from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from django.utils.functional import cached_property
from django.utils.translation import ugettext as _

from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.sms.models import SMS, INCOMING, MessagingSubEvent, MessagingEvent, OUTGOING
from corehq.apps.userreports.util import get_table_name
from custom.abt.reports.filters import UsernameFilter, CountryFilter, LevelOneFilter, LevelTwoFilter, \
    LevelThreeFilter, LevelFourFilter, SubmissionStatusFilter


class LatePMTUsers(SqlData):
    engine_id = 'default'

    @property
    def table_name(self):
        return get_table_name(self.domain, "static-late-pmt")

    @property
    def domain(self):
        return self.config['domain']

    @property
    def filters(self):
        filters = []
        filter_fields = [
            'country',
            'level_1',
            'level_2',
            'level_3',
            'level_4',
        ]
        for filter_field in filter_fields:
            if filter_field in self.config and self.config[filter_field]:
                filters.append(EQ(filter_field, filter_field))
        if 'user_id' in self.config and self.config['user_id']:
            filters.append(EQ('doc_id', 'user_id'))
        return filters

    @property
    def group_by(self):
        return [
            'user_id',
            'username',
            'phone_number',
            'country',
            'level_1',
            'level_2',
            'level_3',
            'level_4',
        ]

    @property
    def order_by(self):
        return [OrderBy('username')]

    @property
    def columns(self):
        return [
            DatabaseColumn('user_id', SimpleColumn('doc_id', alias='user_id')),
            DatabaseColumn('username', SimpleColumn('username')),
            DatabaseColumn('phone_number', SimpleColumn('phone_number')),
            DatabaseColumn('country', SimpleColumn('country')),
            DatabaseColumn('level_1', SimpleColumn('level_1')),
            DatabaseColumn('level_2', SimpleColumn('level_2')),
            DatabaseColumn('level_3', SimpleColumn('level_3')),
            DatabaseColumn('level_4', SimpleColumn('level_4'))
        ]


class LatePmtReport(GenericTabularReport, CustomProjectReport, DatespanMixin):
    report_title = "Late PMT"
    slug = 'late_pmt'
    name = "Late PMT"

    languages = (
        'en',
        'fra',
        'por'
    )

    fields = [
        DatespanFilter,
        UsernameFilter,
        CountryFilter,
        LevelOneFilter,
        LevelTwoFilter,
        LevelThreeFilter,
        LevelFourFilter,
        SubmissionStatusFilter,
    ]

    @property
    def report_config(self):
        return {
            'domain': self.domain,
            'startdate': self.startdate,
            'enddate': self.enddate,
            'user_id': self.request.GET.get('user_id', ''),
            'country': self.request.GET.get('country', ''),
            'level_1': self.request.GET.get('level_1', ''),
            'level_2': self.request.GET.get('level_2', ''),
            'level_3': self.request.GET.get('level_3', ''),
            'level_4': self.request.GET.get('level_4', ''),
            'submission_status': self.request.GET.get('submission_status', '')
        }

    @property
    def startdate(self):
        return self.request.datespan.startdate

    @property
    def enddate(self):
        return self.request.datespan.end_of_end_day

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_("Missing Report Date")),
            DataTablesColumn(_("Username")),
            DataTablesColumn(_("Phone Number")),
            DataTablesColumn(_("Country")),
            DataTablesColumn(_("Level 1")),
            DataTablesColumn(_("Level 2")),
            DataTablesColumn(_("Level 3")),
            DataTablesColumn(_("Level 4")),
            DataTablesColumn(_("Submission Status")),
        )

    @cached_property
    def get_users_in_group_a(self):
        data = SMS.objects.filter(
            domain=self.domain,
            couch_recipient_doc_type='CommCareUser',
            direction=INCOMING,
            couch_recipient__in=self.get_user_ids,
            date__range=(
                self.startdate,
                self.enddate
            )
        ).exclude(
            text="123"
        ).values('date', 'couch_recipient').annotate(
            number_of_sms=Count('couch_recipient')
        )
        return [(user['date'].date(), user['couch_recipient']) for user in data]

    @cached_property
    def get_users_in_group_b(self):
        data = MessagingSubEvent.objects.filter(
            parent__domain=self.domain,
            parent__recipient_type=MessagingEvent.RECIPIENT_MOBILE_WORKER,
            parent__source=MessagingEvent.SOURCE_KEYWORD,
            xforms_session__isnull=False,
            xforms_session__submission_id__isnull=False,
            recipient_id__in=self.get_user_ids,
            date__range=(
                self.startdate,
                self.enddate
            )
        ).values('date', 'recipient_id')
        return [(user['date'].date(), user['recipient_id']) for user in data]

    @cached_property
    def get_user_ids(self):
        return [user['user_id'] for user in self.get_users]

    @cached_property
    def get_users(self):
        return LatePMTUsers(config=self.report_config).get_data()

    @property
    def rows(self):
        def _to_report_format(date, user, group):
            return [
                date.strftime("%Y-%m-%d"),
                user['username'].split('@')[0],
                user['phone_number'],
                user['country'],
                user['level_1'],
                user['level_2'],
                user['level_3'],
                user['level_4'],
                group
            ]

        def not_in_group(key, group):
            return key not in group

        users = self.get_users
        dates = rrule(
            DAILY,
            dtstart=self.startdate,
            until=self.enddate,
            byweekday=(MO, TU, WE, TH, FR, SA)
        )
        rows = []
        sub_status = self.report_config['submission_status']
        if users:
            group_a = self.get_users_in_group_a
            group_b = self.get_users_in_group_b

            for date in dates:
                for user in users:
                    key = (date.date(), user['user_id'])
                    if not_in_group(key, group_a) and sub_status != 'group_b':
                        group = _('No PMT data Submitted')
                    elif not_in_group(key, group_b) and not not_in_group(key, group_a) and sub_status != 'group_a':
                        group = _('Incorrect PMT data Submitted')
                    else:
                        continue
                    rows.append(_to_report_format(date, user, group))
        return rows
