from __future__ import absolute_import
from __future__ import unicode_literals

from sqlagg.columns import SimpleColumn
from sqlagg.sorting import OrderBy
from django.db.models.aggregates import Count

from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn
from corehq.apps.reports.standard import CustomProjectReport
from django.utils.translation import ugettext as _

from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.sms.models import SMS, INCOMING, MessagingSubEvent, MessagingEvent
from corehq.apps.userreports.util import get_table_name
from custom.abt.reports.filters import UsernameFilter, CountryFilter, LevelOneFilter, LevelTwoFilter, LevelThreeFilter, \
    LevelFourFilter, SubmissionStatusFilter


class LatePMTUsers(SqlData):
    engine_id = 'ucr'

    @property
    def table_name(self):
        return get_table_name(self.domain, "static-late-pmt")

    @property
    def domain(self):
        return self.config['domain']

    @property
    def filters(self):
        filters = []
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
            DatabaseColumn('id', SimpleColumn('user_id')),
            DatabaseColumn('username', SimpleColumn('username')),
            DatabaseColumn('phone_number', SimpleColumn('phone_number')),
            DatabaseColumn('country', SimpleColumn('country')),
            DatabaseColumn('level_1', SimpleColumn('level_1')),
            DatabaseColumn('level_2', SimpleColumn('level_2')),
            DatabaseColumn('level_3', SimpleColumn('level_3')),
            DatabaseColumn('level_4', SimpleColumn('level_4'))
        ]


class LatePmtReport(CustomProjectReport, GenericTabularReport):
    report_title = "Late PMT"
    slug = 'late_pmt'
    name = "Late PMT"

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
        config = {
            'domain': self.domain
        }
        return config

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_("Date and Time Submitted")),
            DataTablesColumn(_("Username")),
            DataTablesColumn(_("Phone Number")),
            DataTablesColumn(_("Country")),
            DataTablesColumn(_("Level 1")),
            DataTablesColumn(_("Level 2")),
            DataTablesColumn(_("Level 3")),
            DataTablesColumn(_("Level 4")),
            DataTablesColumn(_("Submission Status")),
        )

    @property
    def get_users(self):
        return LatePMTUsers(config=self.report_config).get_data()

    @property
    def rows(self):
        users = self.get_users
        users_pmt_group_A = SMS.objects.filter(
            domain=self.domain,
            couch_recipient_doc_type='CommCareUser',
            direction=INCOMING
        ).values('couch_recipient').annotate(
            number_of_sms=Count('couch_recipient')
        )
        users_pmt_group_C = MessagingSubEvent.objects.filter(
            parent__domain=self.domain,
            parent__recipient_type=MessagingEvent.RECIPIENT_MOBILE_WORKER,
            parent__source=MessagingEvent.SOURCE_KEYWORD,
            xforms_session__isnull=False,
            xforms_session__submission_id__isnull=False
        ).values('recipient_id')
        return []
