from dimagi.utils.decorators.memoized import memoized
from sqlagg.columns import *
from django.utils.translation import ugettext as _, ugettext_noop
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.sqlreport import DatabaseColumn, SqlData, TableDataFormatter, AggregateColumn
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.apps.users.util import user_id_to_username
from custom.reports.mc.reports.composed import DataProvider, ComposedTabularReport

NO_VALUE = u'\u2014'

HF_MONTHLY_REPORT = [
    {
        'section': ugettext_noop('Home Visits'),
        'columns': [
            'home_visits_pregnant',
            'home_visits_postpartem',
            'home_visits_newborn',
            'home_visits_children',
            'home_visits_other',
            'home_visits_total',
        ]
    },

    {
        'section': ugettext_noop('RDT'),
        'columns': [
            "rdt_positive_children",
            "rdt_positive_adults",
            "rdt_others",
            "rdt_total",
        ]
    },

    {
        'section': ugettext_noop('Diagnosed Cases'),
        'columns': [
            "diagnosed_malaria_child",
            "diagnosed_malaria_adult",
            "diagnosed_diarrhea",
            "diagnosed_ari",
            "diagnosed_total",
        ]
    },

    {
        'section': ugettext_noop('Treated Cases'),
        'columns': [
            "treated_malaria",
            "treated_diarrhea",
            "treated_ari",
            "treated_total",
        ]
    },

    {
        'section': ugettext_noop('Transfers'),
        'columns': [
            "transfer_malnutrition",
            "transfer_incomplete_vaccination",
            "transfer_danger_signs",
            "transfer_prenatal_consult",
            # "transfer_missing_malaria_meds",
            "transfer_other",
            "transfer_total",
        ]
    },

    {
        'section': ugettext_noop('Deaths'),
        'columns': [
            "deaths_newborn",
            "deaths_children",
            "deaths_mothers",
            "deaths_other",
            "deaths_total",
        ]
    },
    {
        'section': ugettext_noop('Health Education'),
        'columns': [
            "heath_ed_talks",
            "heath_ed_participants",
        ]
    },
]

# todo: need to add additional columns for district report
DISTRICT_MONTHLY_REPORT = HF_MONTHLY_REPORT

DISTRICT_WEEKLY_REPORT = [
    {
        'section': ugettext_noop('Home Visits'),
        'columns': [
            'home_visits_newborn_reg',
            'home_visits_child_reg',
            'home_visits_pregnant',
            'home_visits_non_pregnant',
            'home_visits_followup',
            'home_visits_total',
        ]
    },
    {
        'section': ugettext_noop('Deaths in the Community'),
        'columns': [
            "deaths_children",
        ]
    },
    # {
    #     'section': ugettext_noop('Stock Balance'),
    #     'columns': [
    #         "heath_ed_talks",
    #         "heath_ed_participants",
    #     ]
    # },
    {
        'section': ugettext_noop('Validation of Diagnosis and Treatment'),
        'columns': [
            # todo: display num/denom groupings
            {
                'slug': ugettext_noop('patients_given_pneumonia_meds'),
                'columns': ('patients_given_pneumonia_meds_num', 'patients_given_pneumonia_meds_denom'),
            },
            {
                'slug': ugettext_noop('patients_given_diarrhoea_meds'),
                'columns': ('patients_given_diarrhoea_meds_num', 'patients_given_diarrhoea_meds_denom'),
            },
            {
                'slug': ugettext_noop('patients_given_malaria_meds'),
                'columns': ('patients_given_malaria_meds_num', 'patients_given_malaria_meds_denom'),
            },
            {
                'slug': ugettext_noop('patients_correctly_referred'),
                'columns': ('patients_correctly_referred_num', 'patients_correctly_referred_denom'),
            },
            'cases_rdt_not_done',
            'cases_danger_signs_not_referred',
            'cases_no_malaria_meds',
        ]
    },

]

HF_WEEKLY_REPORT = [
    {
        'section': ugettext_noop('Home Visits'),
        'columns': [
            'home_visits_newborn',
            'home_visits_children',
            'home_visits_adult',
            'home_visits_total',
        ]
    },
    {
        'section': ugettext_noop('Transferred Cases'),
        'columns': [
            'cases_transferred',
            'home_visits_followup',
            {
                'slug': ugettext_noop('patients_given_pneumonia_meds'),
                'columns': ('patients_given_pneumonia_meds_num', 'patients_given_pneumonia_meds_denom'),
            },
            {
                'slug': ugettext_noop('patients_given_diarrhoea_meds'),
                'columns': ('patients_given_diarrhoea_meds_num', 'patients_given_diarrhoea_meds_denom'),
            },
            {
                'slug': ugettext_noop('patients_given_malaria_meds'),
                'columns': ('patients_given_malaria_meds_num', 'patients_given_malaria_meds_denom'),
            },
            {
                'slug': ugettext_noop('patients_correctly_referred'),
                'columns': ('patients_correctly_referred_num', 'patients_correctly_referred_denom'),
            },
            'cases_rdt_not_done',
        ]
    },

]

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
        num=num,
        denom=denom,
    )

def _to_column(coldef):

    def _slug_to_raw_column(slug):
        return SumColumn('%s_total' % slug)

    if isinstance(coldef, dict):
        return AggregateColumn(
            coldef['slug'],
            _fraction,
            *(_slug_to_raw_column(s) for s in coldef['columns'])
        )
    return DatabaseColumn(coldef, _slug_to_raw_column(coldef))

class Section(SqlData):
    """
    A way to represent sections in a report. I wonder if we should genericize/pull this out.
    """
    def __init__(self, report, section_def):
        self.report = report
        self.section_def = section_def

    def __getattribute__(self, item):
        if item in ['table_name', 'group_by', 'filters', 'filter_values', 'keys']:
            return getattr(self.report, item)
        return super(Section, self).__getattribute__(item)

    def title(self):
        return self.section_def['section']

    @property
    @memoized
    def columns(self):
        return [_to_column(col) for col in self.section_def['columns']]

    @property
    @memoized
    def rows(self):
        raw_data = list(TableDataFormatter.from_sqldata(self, no_value=NO_VALUE).format())
        ret = transpose(self.columns, raw_data)
        return ret


class McSqlData(SqlData):

    table_name = "mc-inscale_MalariaConsortiumFluff"

    def __init__(self, sections, domain, datespan):
        self.domain = domain
        self.datespan = datespan
        self._sections = sections

    @property
    def group_by(self):
        return ['user_id']

    @property
    def filters(self):
        return ["domain = :domain", "date between :startdate and :enddate"]

    @property
    @memoized
    def sections(self):
        return [Section(self, section) for section in self._sections]


    @property
    def filter_values(self):
        return dict(domain=self.domain,
                    startdate=self.datespan.startdate_param_utc,
                    enddate=self.datespan.enddate_param_utc)

    @property
    def columns(self):
        user = DatabaseColumn("User", SimpleColumn("user_id"))
        columns = [user]
        for section in self.sections:
            columns.extend(section.columns)
        return columns


class MCSectionedDataProvider(DataProvider):

    def __init__(self, sqldata):
        self.sqldata = sqldata

    @memoized
    def user_column(self, user_id):
        return DataTablesColumn(user_id_to_username(user_id))


    def headers(self):
        return DataTablesHeader(DataTablesColumn(_('Indicator')),
                                *[self.user_column(u) for u in [r[0] for r in self._raw_rows]])

    @property
    @memoized
    def _raw_rows(self):
        return list(TableDataFormatter.from_sqldata(self.sqldata, no_value=NO_VALUE).format())

    def rows(self):
        # a bit of a hack. rows aren't really rows, but the template knows
        # how to deal with them
        return self.sqldata.sections


class MCBase(ComposedTabularReport, CustomProjectReport, DatespanMixin):
    # stuff like this feels silly but there doesn't seem to be an easy
    # way to break out of the inheritance pattern and be DRY
    exportable = True
    emailable = True
    report_template_path = "mc/reports/sectioned_tabular.html"
    fields = ['corehq.apps.reports.fields.DatespanField']
    SECTIONS = None  # override

    def __init__(self, request, base_context=None, domain=None, **kwargs):
        super(MCBase, self).__init__(request, base_context, domain, **kwargs)
        assert self.SECTIONS is not None
        sqldata = McSqlData(self.SECTIONS, domain, self.datespan)
        self.data_provider = MCSectionedDataProvider(sqldata)

class HeathFacilityMonthly(MCBase):
    slug = 'hf_monthly'
    name = ugettext_noop("Health Facility Monthly Report")
    SECTIONS = HF_MONTHLY_REPORT

class DistrictMonthly(MCBase):
    slug = 'district_monthly'
    name = ugettext_noop("District Monthly Report")
    SECTIONS = DISTRICT_MONTHLY_REPORT

class DistrictWeekly(MCBase):
    slug = 'district_weekly'
    name = ugettext_noop("District Weekly Report")
    SECTIONS = DISTRICT_WEEKLY_REPORT

class HealthFacilityWeekly(MCBase):
    slug = 'hf_weekly'
    name = ugettext_noop("Health Facility Weekly Report")
    SECTIONS = HF_WEEKLY_REPORT
