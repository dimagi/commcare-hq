from django.utils.translation import ugettext_lazy
from sqlagg.columns import SimpleColumn
from sqlagg.sorting import OrderBy

from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn
from corehq.apps.userreports.util import get_table_name
from corehq.sql_db.connections import DEFAULT_ENGINE_ID


class FilterDataSource(SqlData):
    engine_id = DEFAULT_ENGINE_ID

    def __init__(self, domain, loc_level):
        self.config = {}
        self.domain = domain
        self.loc_level = loc_level

    @property
    def table_name(self):
        return get_table_name(self.domain, "static-late-pmt")

    @property
    def filters(self):
        filters = []
        return filters

    @property
    def group_by(self):
        return [self.loc_level]

    @property
    def order_by(self):
        return [OrderBy(self.loc_level)]

    @property
    def columns(self):
        return [
            DatabaseColumn(self.loc_level, SimpleColumn(self.loc_level))
        ]


class UserFilterDataSource(SqlData):
    engine_id = DEFAULT_ENGINE_ID

    def __init__(self, domain):
        self.config = {}
        self.domain = domain

    @property
    def table_name(self):
        return get_table_name(self.domain, "static-late-pmt")

    @property
    def filters(self):
        filters = []
        return filters

    @property
    def group_by(self):
        return ['doc_id', 'username']

    @property
    def order_by(self):
        return [OrderBy('username')]

    @property
    def columns(self):
        return [
            DatabaseColumn('doc_id', SimpleColumn('doc_id')),
            DatabaseColumn('username', SimpleColumn('username'))
        ]


class VectorLinkLocFilter(BaseSingleOptionFilter):
    default_text = 'All'

    @property
    def options(self):
        data = FilterDataSource(self.domain, self.slug).get_data()
        options = [(x[self.slug], x[self.slug]) for x in data]
        return options


class UsernameFilter(VectorLinkLocFilter):
    slug = 'user_id'
    label = ugettext_lazy('Username')

    @property
    def options(self):
        data = UserFilterDataSource(self.domain).get_data()
        options = [(x['doc_id'], x['username']) for x in data]
        return options


class CountryFilter(VectorLinkLocFilter):
    slug = 'country'
    label = ugettext_lazy('Country')


class LevelOneFilter(VectorLinkLocFilter):
    slug = 'level_1'
    label = ugettext_lazy('Level 1')


class LevelTwoFilter(VectorLinkLocFilter):
    slug = 'level_2'
    label = ugettext_lazy('Level 2')


class LevelThreeFilter(VectorLinkLocFilter):
    slug = 'level_3'
    label = ugettext_lazy('Level 3')


class LevelFourFilter(VectorLinkLocFilter):
    slug = 'level_4'
    label = ugettext_lazy('Level 4')


class SubmissionStatusFilter(BaseSingleOptionFilter):
    slug = 'submission_status'
    label = ugettext_lazy('Submission Status')
    default_text = 'All'

    @property
    def options(self):
        return [
            ('group_a', 'No PMT Data Submitted'),
            ('group_b', 'Incorrect PMT Data Submitted')
        ]
