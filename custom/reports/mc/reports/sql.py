from dimagi.utils.couch.database import get_db
from dimagi.utils.decorators.memoized import memoized
from sqlagg.columns import *
from django.utils.translation import ugettext as _, ugettext_noop
from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.sqlreport import DatabaseColumn, SqlData, AggregateColumn, DataFormatter, TableDataFormat
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import user_id_to_username
from couchforms.models import XFormInstance
from custom.reports.mc.models import WEEKLY_SUMMARY_XMLNS
from .definitions import *
from .composed import DataProvider, ComposedTabularReport


NO_VALUE = u'\u2014'

def transpose(columns, data):
    return [[column.data_tables_column.html] + [r[i] for r in data] \
            for i, column in enumerate(columns)]

def _fraction(num, denom):

    _pct = lambda num, denom: float(num or 0) / float(denom) if denom else None
    _fmt_pct = lambda pct: ('%.1f%%' % (100. * pct))

    pct = _pct(num, denom)
    if pct is None:
        return NO_VALUE
    return '{pct} ({num}/{denom})'.format(
        pct=_fmt_pct(pct),
        num=num or 0,
        denom=denom,
    )

def _to_column(coldef):

    def _slug_to_raw_column(slug):
        return SumColumn('%s_total' % slug)

    if isinstance(coldef, dict):
        return AggregateColumn(
            _(coldef['slug']),
            _fraction,
            [_slug_to_raw_column(s) for s in coldef['columns']]
        )
    return DatabaseColumn(_(coldef), _slug_to_raw_column(coldef))

class Section(object):
    """
    A way to represent sections in a report. I wonder if we should genericize/pull this out.
    """
    def __init__(self, report, section_def):
        self.report = report
        self.section_def = section_def

    @property
    def title(self):
        return _(self.section_def['section'])

    @property
    def column_slugs(self):
        return self.section_def['columns']


class SqlSection(Section, SqlData):
    """
    A way to represent sections in a report. I wonder if we should genericize/pull this out.
    """
    def __getattribute__(self, item):
        if item in ['table_name', 'group_by', 'filters', 'filter_values', 'keys']:
            return getattr(self.report, item)
        return super(Section, self).__getattribute__(item)

    @property
    @memoized
    def columns(self):
        return [_to_column(col) for col in self.column_slugs]

    @property
    @memoized
    def rows(self):
        formatter = DataFormatter(TableDataFormat(self.columns, no_value=NO_VALUE))
        raw_data = list(formatter.format(self.data, keys=self.keys, group_by=self.group_by))
        ret = transpose(self.columns, raw_data)
        return ret

class FormPropertySection(Section):
    """
    A section that grabs the most recent form of a given type in a given window
    and emits some data from it
    """

    @property
    def xmlns(self):
        return self.section_def['xmlns']


    @property
    @memoized
    def rows(self):
        domain = self.report.filter_values['domain']
        startdate = self.report.filter_values['startdate']
        enddate = self.report.filter_values['enddate']
        key_base = 'submission xmlns user'
        # todo this will do one couch view hit per relevant user. could be optimized to sql or something if desired
        user_ids = self.report.get_user_ids()
        rows = []
        for user in user_ids:
            last_submission = XFormInstance.get_db().view('reports_forms/all_forms',
                startkey=[key_base, domain, self.xmlns, user, enddate],
                endkey=[key_base, domain, self.xmlns, user, startdate],
                limit=1,
                reduce=False,
                include_docs=True,
                descending=True,
            ).one()
            if last_submission:
                wrapped = XFormInstance.wrap(last_submission['doc'])
                user_row = [wrapped.xpath(path) for path in self.column_slugs]
            else:
                user_row = [NO_VALUE] * len(self.column_slugs)
            rows.append(user_row)


        # transpose
        return [[_(col)] + [r[i] for r in rows] for i, col in enumerate(self.column_slugs)]


class McSqlData(SqlData):

    table_name = "mc-inscale_MalariaConsortiumFluff"

    def __init__(self, sections, domain, datespan, fixture_type, fixture_item):
        self.domain = domain
        self.datespan = datespan
        self.fixture_type = fixture_type
        self.fixture_item = fixture_item
        self._sections = sections

    @memoized
    def _get_users_matching_location(self, fixture_item, fixture_type):
        # todo: optimize
        return filter(
            lambda u: u.user_data.get(fixture_type.tag, None) == fixture_item.fields.get('name'),
            CommCareUser.by_domain(fixture_item.domain)
        )


    @property
    def group_by(self):
        return ['user_id']

    @property
    def filters(self):
        base_filters = ["domain = :domain", "date between :startdate and :enddate"]
        if self.fixture_item is not None:
            base_filters.append('"user_id" in :userids')
        return base_filters

    @property
    @memoized
    def sections(self):
        def _section_class(section_def):
            return {
                'form_lookup': FormPropertySection,
            }.get(section_def.get('type'), SqlSection)
        return [_section_class(section)(self, section) for section in self._sections]

    @memoized
    def all_rows(self):
        return [value for s in self.sections for value in s.rows]

    @property
    def filter_values(self):
        base_filter_values = {
            'domain': self.domain,
            'startdate': self.datespan.startdate_param_utc,
            'enddate': self.datespan.enddate_param_utc,
        }
        if self.fixture_item is not None:
            user_ids = tuple(u._id for u in self._get_users_matching_location(self.fixture_item, self.fixture_type))
            if user_ids:
                base_filter_values['userids'] = user_ids
            else:
                base_filter_values['userids'] = ('__EMPTY__',)
        return base_filter_values

    @property
    def user_column(self):
        return DatabaseColumn("User", SimpleColumn("user_id"))

    @property
    def columns(self):
        columns = [self.user_column]
        for section in self.sections:
            columns.extend(section.columns)
        return columns

    @memoized
    def get_user_ids(self):
        # make an empty copy of this to just get the ids out
        header_sql_data = McSqlData(
            [], # blank sections
            self.domain,
            self.datespan,
            self.fixture_type,
            self.fixture_item
        )
        user_formatter = DataFormatter(TableDataFormat([self.user_column], no_value=NO_VALUE))
        results = list(user_formatter.format(header_sql_data.data,
                                             keys=header_sql_data.keys,
                                             group_by=header_sql_data.group_by))
        return [r[0] for r in results]


class MCSectionedDataProvider(DataProvider):

    def __init__(self, sqldata):
        self.sqldata = sqldata

    @memoized
    def user_column(self, user_id):
        return DataTablesColumn(user_id_to_username(user_id))


    def headers(self):
        return DataTablesHeader(DataTablesColumn(_('Indicator')),
                                *[self.user_column(u) for u in self.sqldata.get_user_ids()])

    @memoized
    def rows(self):
        return self.sqldata.all_rows()

    @property
    @memoized
    def sections(self):
        return self.sqldata.sections


def section_context(report):
    return {"sections": report.sections}


class MCBase(ComposedTabularReport, CustomProjectReport, DatespanMixin):
    # stuff like this feels silly but there doesn't seem to be an easy
    # way to break out of the inheritance pattern and be DRY
    exportable = True
    emailable = True
    report_template_path = "mc/reports/sectioned_tabular.html"
    fields = [
        'corehq.apps.reports.fields.DatespanField',
    ]
    SECTIONS = None  # override
    extra_context_providers = [section_context]

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return user and user.is_previewer()

    def __init__(self, request, base_context=None, domain=None, **kwargs):
        super(MCBase, self).__init__(request, base_context, domain, **kwargs)
        assert self.SECTIONS is not None
        fixture = self.request_params.get('fixture_id', None)
        if fixture:
            type_string, id = fixture.split(":")
            results = FixtureDataType.by_domain_tag(domain, type_string)
            fixture_type = results.one()
            fixture_item = FixtureDataItem.get(id)
        else:
            fixture_item = None
            fixture_type = None

        sqldata = McSqlData(self.SECTIONS, domain, self.datespan, fixture_type, fixture_item)
        self.data_provider = MCSectionedDataProvider(sqldata)

    @property
    def sections(self):
        return self.data_provider.sections

class HeathFacilityMonthly(MCBase):
    slug = 'hf_monthly'
    fields = [
        'corehq.apps.reports.fields.DatespanField',
        'custom.reports.mc.reports.fields.HealthFacilityField',
    ]
    name = ugettext_noop("Health Facility Monthly Report")
    SECTIONS = HF_MONTHLY_REPORT

class DistrictMonthly(MCBase):
    fields = [
        'corehq.apps.reports.fields.DatespanField',
        'custom.reports.mc.reports.fields.DistrictField',
    ]
    slug = 'district_monthly'
    name = ugettext_noop("District Monthly Report")
    SECTIONS = DISTRICT_MONTHLY_REPORT

class DistrictWeekly(MCBase):
    fields = [
        'corehq.apps.reports.fields.DatespanField',
        'custom.reports.mc.reports.fields.DistrictField',
    ]
    slug = 'district_weekly'
    name = ugettext_noop("District Weekly Report")
    SECTIONS = DISTRICT_WEEKLY_REPORT

class HealthFacilityWeekly(MCBase):
    fields = [
        'corehq.apps.reports.fields.DatespanField',
        'custom.reports.mc.reports.fields.HealthFacilityField',
    ]
    slug = 'hf_weekly'
    name = ugettext_noop("Health Facility Weekly Report")
    SECTIONS = HF_WEEKLY_REPORT
