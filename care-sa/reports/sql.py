from sqlagg.columns import *
from corehq.apps.reports.sqlreport import SqlTabularReport, DatabaseColumn
from corehq.apps.reports.fields import AsyncDrillableField, GroupField
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin

REPORT_COLUMNS = [
    ('HIV Counseling', 'hiv_counseling'),
    ('Individuals HIV tested', 'hiv_tested'),
    #TODO NO DATA ('Individuals HIV Positive ', 'hiv_positive'),
    ('Newly diagnosed HIV+ indv scr for TB', 'new_hiv_tb_screen'),  # 1d
    #TODO NO DATA ('Individuals scr for TB (status unknown)', 'hiv_known_screened'),  # 1e
    #TODO NO DATA ('Individuals ref to PHCF with signs & symptoms of TB', 'referred_tb_signs'),  # 1f
    #('Individuals ref for TB diagnosis to PHCF who receive results', 'TODO'),  # 1g
    #TODO NO DATA ('Individuals HIV infected ref for CD4 count test in a PHCF', 'referred_for_cdf_new'),  # 1h
    ('Individuals HIV infected provided with CD4 count test results',
     'new_hiv_cd4_results'),  # 1i
    #TODO NO DATA ('Individuals HIV infected provided with CD4 count test results from previous months',
    # 'new_hiv_in_care_program'),  # 1k
    ('People tested as individuals', 'individual_tests'),  # 1l
    #TODO NO DATA ('People tested as couples', 'couple_tests'),  # 1m
]


class ProvinceField(AsyncDrillableField):
    label = "Province"
    slug = "province"
    hierarchy = [{"type": "province", "display": "name"}]


class CBOField(GroupField):
    name = 'CBO'
    default_option = 'All'


class TestingAndCounseling(SqlTabularReport,
                           CustomProjectReport,
                           DatespanMixin):
    exportable = True
    emailable = True
    slug = 'tac_slug'
    name = "Testing and Counseling"
    table_name = "care-ihapc-live_CareSAFluff"

    fields = [
        'corehq.apps.reports.fields.DatespanField',
        'care-sa.reports.sql.ProvinceField',
        'care-sa.reports.sql.CBOField',
    ]

    def selected_province(self):
        fixture = self.request.GET.get('fixture_id', "")
        return fixture.split(':')[1] if fixture else None

    def selected_cbo(self):
        group = self.request.GET.get('group', '')
        return group

    @property
    def filters(self):
        filters = [
            "domain = :domain",
            "date between :startdate and :enddate",
        ]

        if self.selected_province():
            filters.append("province = :province")
        if self.selected_cbo():
            filters.append("cbo = :cbo")

        return filters

    @property
    def group_by(self):
        return ['user_id']

    @property
    def filter_values(self):
        return dict(
            domain=self.domain,
            startdate=self.datespan.startdate_param_utc,
            enddate=self.datespan.enddate_param_utc,
            province=self.selected_province(),
            cbo=self.selected_cbo(),
        )

    @property
    def columns(self):
        user = DatabaseColumn("User", "user_id", column_type=SimpleColumn)
        columns = [user]

        for text, column in REPORT_COLUMNS:
            columns.append(DatabaseColumn(text, '%s_total' % column))

        return columns

    @property
    def keys(self):
        [self.domain]
