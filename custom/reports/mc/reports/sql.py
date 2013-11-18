from collections import defaultdict
from dimagi.utils.decorators.memoized import memoized
from sqlagg.columns import *
from django.utils.translation import ugettext as _, ugettext_noop
from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.sqlreport import DatabaseColumn, SqlData, AggregateColumn, DataFormatter, TableDataFormat, DictDataFormat
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import raw_username
from couchforms.models import XFormInstance
from .definitions import *
from .composed import DataProvider, ComposedTabularReport


NO_VALUE = u'\u2014'

def transpose(columns, data):
    return [[column.data_tables_column.html] + [r[i] for r in data] \
            for i, column in enumerate(columns)]

class Fraction(object):

    def __init__(self, num, denom):
        self.num = num or 0
        self.denom = denom or 0

    def is_empty(self):
        return not (bool(self.num) or bool(self.denom))

    def pct(self):
        return (float(self.num) / float(self.denom)) * 100

    def pct_display(self):
        return '%.1f%%' % (100. * self.pct())

    def __unicode__(self):
        if self.is_empty():
            return NO_VALUE
        else:
            return '{pct:.1f}% ({num}/{denom})'.format(
                pct=self.pct(),
                num=self.num,
                denom=self.denom,
            )

    def combine(self, other):
        if isinstance(other, Fraction):
            return Fraction(self.num + other.num, self.denom + other.denom)
        elif not other or other == NO_VALUE:
            return self
        else:
            raise ValueError("Can't combine %s (%s) with a fraction" % (other, type(other)))


def _to_column(coldef):

    def _slug_to_raw_column(slug):
        return SumColumn('%s_total' % slug)

    if isinstance(coldef, dict):
        return AggregateColumn(
            _(coldef['slug']),
            Fraction,
            [_slug_to_raw_column(s) for s in coldef['columns']],
            sortable=False,
            slug=coldef['slug'],
        )
    return DatabaseColumn(_(coldef), _slug_to_raw_column(coldef), sortable=False)

def _empty_row(len):
    return [NO_VALUE] * len

class UserDataFormat(TableDataFormat):

    def __init__(self, columns, users):
        self.columns = columns
        self.no_value = NO_VALUE
        self.users = users

    def get_headers(self):
        return [raw_username(u.username) for u in self.users]

    def format_output(self, row_generator):
        raw_data = dict(row_generator)
        for user in self.users:
            if user._id in raw_data:
                yield raw_data[user._id]
            else:
                yield _empty_row(len(self.columns))

class FacilityDataFormat(TableDataFormat):

    def __init__(self, columns, users):
        self.columns = columns
        self.no_value = NO_VALUE
        self.users = users
        self.facility_user_map = defaultdict(lambda: [])
        for u in users:
            self.facility_user_map[u.user_data.get('health_facility') or NO_VALUE].append(u)

    def get_headers(self):
        return sorted(self.facility_user_map.keys())

    def format_output(self, row_generator):
        raw_data = dict(row_generator)

        def _combine_rows(row1, row2):
            def _combine(a, b):
                def _int(val):
                    return 0 if val == NO_VALUE else int(val)

                if a == NO_VALUE and b == NO_VALUE:
                    return NO_VALUE
                elif isinstance(a, Fraction):
                    return a.combine(b)
                elif isinstance(b, Fraction):
                    return b.combine(a)
                else:
                    return _int(a) + _int(b)

            if not row1:
                return row2
            return [_combine(row1[i], row2[i]) for i in range(len(row1))]

        for facility in sorted(self.facility_user_map.keys()):
            users = self.facility_user_map[facility]
            data = []
            for user in users:
                if user._id in raw_data:
                    user_data = raw_data[user._id]
                else:
                    user_data = _empty_row(len(self.columns))
                data = _combine_rows(data, user_data)
            yield data


class Section(object):
    """
    A way to represent sections in a report. I wonder if we should genericize/pull this out.
    """
    def __init__(self, report, section_def, format_class):
        self.report = report
        self.section_def = section_def
        self.format_class  = format_class

    @property
    def title(self):
        return _(self.section_def['section'])

    @property
    def column_slugs(self):
        return self.section_def['columns']


class SqlSection(Section, SqlData):
    """
    A sql-based implementation of sections
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
        formatter = DataFormatter(self.format_class(self.columns, self.report.get_users()))
        raw_data = formatter.format(self.data, keys=self.keys, group_by=self.group_by)
        return transpose(self.columns, list(raw_data))


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
            rows.append((user, user_row))

        # format
        formatted_rows = list(self.report.format.format_output(rows))
        # transpose
        return [[_(col)] + [r[i] for r in formatted_rows] for i, col in enumerate(self.column_slugs)]


class McSqlData(SqlData):

    table_name = "mc-inscale_MalariaConsortiumFluff"

    def __init__(self, sections, format_class, domain, datespan, fixture_type, fixture_item):
        self.format_class = format_class
        self.domain = domain
        self.datespan = datespan
        self.fixture_type = fixture_type
        self.fixture_item = fixture_item
        self._sections = sections

    @property
    @memoized
    def format(self):
        return self.format_class([], self.get_users())

    def get_headers(self):
        return self.format.get_headers()

    @memoized
    def get_data(self, slugs=None):
        # only overridden to memoize
        return super(McSqlData, self).get_data(slugs)

    @memoized
    def get_users(self):
        def _is_ape(user):
            return user.user_data.get('level') == 'APE'

        def _matches_location(user):
            def _tag_to_user_data(tag):
                return {
                    'hf': 'health_facility',
                }.get(tag) or tag

            if self.fixture_type and self.fixture_item:
                return user.user_data.get(_tag_to_user_data(self.fixture_type.tag), None) == self.fixture_item.fields_without_attributes.get('name')
            else:
                return True

        unfiltered_users = CommCareUser.by_domain(self.domain)
        filtered_users = filter(
            lambda u: _is_ape(u) and _matches_location(u),
            unfiltered_users,
        )
        return sorted(filtered_users, key=lambda u: u.username)


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
        return [_section_class(section)(self, section, self.format_class) for section in self._sections]

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
            user_ids = tuple(u._id for u in self.get_users())
            if user_ids:
                base_filter_values['userids'] = user_ids
            else:
                base_filter_values['userids'] = ('__EMPTY__',)
        return base_filter_values

    @property
    def user_column(self):
        return DatabaseColumn("User", SimpleColumn("user_id"), sortable=False)

    @property
    def columns(self):
        columns = [self.user_column]
        for section in self.sections:
            columns.extend(section.columns)
        return columns

    @memoized
    def get_user_ids(self):
        return [u._id for u in self.get_users()]

class MCSectionedDataProvider(DataProvider):

    def __init__(self, sqldata):
        self.sqldata = sqldata


    def headers(self):
        return DataTablesHeader(DataTablesColumn(_('Indicator')),
                                *[DataTablesColumn(header) for header in self.sqldata.get_headers()])

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
    format_class = None # override
    extra_context_providers = [section_context]

    def __init__(self, request, base_context=None, domain=None, **kwargs):
        super(MCBase, self).__init__(request, base_context, domain, **kwargs)
        assert self.SECTIONS is not None
        assert self.format_class is not None
        fixture = self.request_params.get('fixture_id', None)
        if fixture:
            type_string, id = fixture.split(":")
            results = FixtureDataType.by_domain_tag(domain, type_string)
            fixture_type = results.one()
            fixture_item = FixtureDataItem.get(id)
        else:
            fixture_item = None
            fixture_type = None

        sqldata = McSqlData(self.SECTIONS, self.format_class, domain, self.datespan, fixture_type, fixture_item)
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
    format_class = UserDataFormat

class DistrictMonthly(MCBase):
    fields = [
        'corehq.apps.reports.fields.DatespanField',
        'custom.reports.mc.reports.fields.DistrictField',
    ]
    slug = 'district_monthly'
    name = ugettext_noop("District Monthly Report")
    SECTIONS = DISTRICT_MONTHLY_REPORT
    format_class = FacilityDataFormat

class DistrictWeekly(MCBase):
    fields = [
        'corehq.apps.reports.fields.DatespanField',
        'custom.reports.mc.reports.fields.DistrictField',
    ]
    slug = 'district_weekly'
    name = ugettext_noop("District Weekly Report")
    SECTIONS = DISTRICT_WEEKLY_REPORT
    format_class = FacilityDataFormat

def _int(str):
    try:
        return int(str or 0)
    except ValueError:
        return 0


def _missing(fraction):
    return fraction.denom - fraction.num


def _messages(hf_user_data):
    if hf_user_data is not None:
        visits = _int(hf_user_data['home_visits_children_total'])
        if visits > 26:
            yield _(HF_WEEKLY_MESSAGES['msg_children']).format(number=visits)

        pneumonia = _missing(hf_user_data['patients_given_pneumonia_meds'])
        if pneumonia > 0:
            yield _(HF_WEEKLY_MESSAGES['msg_pneumonia']).format(number=pneumonia)

        diarrhoea = _missing(hf_user_data['patients_given_diarrhoea_meds'])
        if diarrhoea > 0:
            yield _(HF_WEEKLY_MESSAGES['msg_diarrhoea']).format(number=diarrhoea)

        malaria = _missing(hf_user_data['patients_given_malaria_meds'])
        if malaria > 0:
            yield _(HF_WEEKLY_MESSAGES['msg_malaria']).format(number=malaria)

        missing_ref = _missing(hf_user_data['patients_correctly_referred'])
        if missing_ref == 0:
            yield _(HF_WEEKLY_MESSAGES['msg_good_referrals'])
        else:
            yield _(HF_WEEKLY_MESSAGES['msg_bad_referrals']).format(number=missing_ref)

        rdt = _int(hf_user_data['cases_rdt_not_done_total'])
        if rdt > 0:
            yield _(HF_WEEKLY_MESSAGES['msg_rdt']).format(number=rdt)


def hf_message_content(report):
    if report.needs_filters:
        return {}
    data_by_user = dict((d['user_id'], d) for d in report.data_provider.sqldata.get_data())
    def _user_section(user):
        user_data = data_by_user.get(user._id, None)
        return {
            'username': raw_username(u.username),
            'msgs': list(_messages(user_data)),
        }
    return {
        'hf_messages': [_user_section(u) for u in report.data_provider.sqldata.get_users()]
    }


class HealthFacilityWeekly(MCBase):
    report_template_path = "mc/reports/hf_weekly.html"
    extra_context_providers = [section_context, hf_message_content]
    fields = [
        'corehq.apps.reports.fields.DatespanField',
        'custom.reports.mc.reports.fields.HealthFacilityField',
    ]
    slug = 'hf_weekly'
    name = ugettext_noop("Health Facility Weekly Report")
    SECTIONS = HF_WEEKLY_REPORT
    format_class = UserDataFormat
