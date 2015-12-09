from collections import OrderedDict
import re
from sqlagg.base import AliasColumn
from sqlagg.filters import EQ, OR, AND, BETWEEN, NOTEQ
from corehq.apps.userreports.sql import get_table_name
from corehq.toggles import USER_CONFIGURABLE_REPORTS
from dimagi.utils.decorators.memoized import memoized
from sqlagg.columns import *
from django.utils.translation import ugettext as _, ugettext_noop
from corehq.apps.fixtures.models import FixtureDataItem
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.sqlreport import DatabaseColumn, SqlData, AggregateColumn, DataFormatter,\
    SqlTabularReport, DictDataFormat
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin, ProjectReportParametersMixin
from corehq.apps.users.util import raw_username
from .definitions import *


NO_VALUE = u'\u2014'


def _int(str):
    try:
        return int(str['sort_key'] or 0)
    except ValueError:
        return 0
    except TypeError:
        return 0


def _missing(fraction):
    m = re.search("([0-9]+)/([0-9]+)", fraction['sort_key'])
    if m:
        return int(m.group(2)) - int(m.group(1))
    else:
        return 0


def _messages(hf_user_data):
    if hf_user_data is not None:
        visits = _int(hf_user_data['home_visits_total'])
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

        rdt = _int(hf_user_data['cases_rdt_not_done'])
        if rdt > 0:
            yield _(HF_WEEKLY_MESSAGES['msg_rdt']).format(number=rdt)


def hf_message_content(report):
    if report.needs_filters:
        return {}

    def _user_section(username, data):
        return {
            'username': raw_username(username),
            'msgs': list(_messages(data)),
        }
    return {
        'hf_messages': [_user_section(u, v) for u, v in report.records.iteritems()]
    }


def add_all(*args):
    return sum([(a or 0) for a in args])


def percent_format(x, y):
    num = float(x or 0)
    denom = float(y or 1)
    return "%.1f%% (%s/%s)" % (num * 100 / denom, x or '0', y or '0')


class McMixin(object):
    slug = None

    @property
    def group_by(self):
        r_type = self.slug.split('_')[0]
        if r_type == 'district':
            return ['hf']
        else:
            return ['user_name']

    @property
    def first_column(self):
        r_type = self.slug.split('_')[0]
        if r_type == 'district':
            col_name = 'hf'
        else:
            col_name = 'user_name'

        def format(data):
            if col_name == 'user_name':
                return raw_username(data)
            else:
                return data
        return DatabaseColumn("Indicator", SimpleColumn(col_name), format)

    @property
    def filters(self):
        filters = [BETWEEN('date', 'startdate', 'enddate'), NOTEQ('hf', 'empty')]
        if 'district' in self.config and self.config['district']:
            filters.append(EQ('district', 'district'))
        elif 'hf' in self.config and self.config['hf']:
            filters.append(EQ('hf', 'hf'))
        return filters


class BaseReport(McMixin, SqlTabularReport, DatespanMixin, CustomProjectReport, ProjectReportParametersMixin):
    report_template_path = "mc/reports/sectioned_tabular.html"
    section = None

    @property
    def engine_id(self):
        return 'ucr'

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], "malaria_consortium")

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return USER_CONFIGURABLE_REPORTS.enabled(user.username)

    @property
    def config(self):
        loc = None
        type = 'loc'
        if 'fixture_id' in self.request_params and self.request_params.get('fixture_id'):
            type, id = self.request_params.get('fixture_id').split(":")
            loc = FixtureDataItem.get(id).fields['name']['field_list'][0]['field_value']
        return {
            'domain': self.domain,
            'startdate': self.datespan.startdate,
            'enddate': self.datespan.enddate,
            type: loc,
            'one': 1,
            'zero': 0,
            'not': -1,
            'empty': ''
        }

    @property
    @memoized
    def records(self):
        formatter = DataFormatter(DictDataFormat(self.columns, no_value=self.no_value))
        return OrderedDict(sorted(formatter.format(self.data, keys=self.keys, group_by=self.group_by).items()))

    @property
    def headers(self):
        r_type = self.slug.split('_')[0]
        if r_type == 'district':
            col_name = 'hf'
        else:
            col_name = 'user_name'

        def format(data):
            if col_name == 'user_name':
                return raw_username(data)
            else:
                return data
        headers = DataTablesHeader()
        headers.add_column(self.columns[0].data_tables_column)
        for head in self.records.keys():
            headers.add_column(DataTablesColumn(format(head)))
        return headers

    @property
    def rows(self):
        def append_rows(x, y, z):
            for row in z:
                try:
                    x.append(row[y])
                except KeyError:
                    x.append(self.no_value)

        data = []
        records = self.records.values()
        get_weekly = False
        weekly_forms = None
        for section in self.section:
            if 'type' in section:
                get_weekly = True
        if get_weekly:
            weekly_forms = WeeklyForms(config=self.config).get_data()
        for section in self.section:
            sec = {'title': _(section['section']), 'rows': []}
            columns = list(section['columns'])
            if 'total_column' in section:
                columns.append(section['total_column'])
            for col in columns:
                r = []
                if 'type' in section:
                    r.append(_("form/stock/" + col))
                    for key in self.records.keys():
                        if key in weekly_forms:
                            values = weekly_forms[key]
                            try:
                                r.append(values[col])
                            except KeyError:
                                r.append(self.no_value)
                        else:
                            r.append(self.no_value)
                else:
                    r.append(_(col))
                    append_rows(r, col, records)
                sec['rows'].append(r)
            data.append(sec)
        return data

    @property
    def export_rows(self):
        def _gen():
            for section in self.rows:
                yield [section['title']]
                for row in section['rows']:
                    yield row
        return list(_gen())


class DistrictWeekly(BaseReport):
    fields = [
        'corehq.apps.reports.filters.dates.DatespanFilter',
        'custom.reports.mc.reports.fields.DistrictField',
    ]
    slug = 'district_weekly_ucr'
    name = "UCR Relatorio Semanal aos Coordinadores do Distrito e os NEDs"
    section = DISTRICT_WEEKLY_REPORT

    @property
    def columns(self):
        return [
            self.first_column,
            DatabaseColumn(_('home_visits_pregnant'),
                           CountColumn('home_visit', alias="home_visits_pregnant",
                                       filters=self.filters + [EQ('home_visit', 'one')])),
            DatabaseColumn(_('home_visits_non_pregnant'),
                           CountColumn('home_visit', alias="home_visits_non_pregnant",
                                       filters=self.filters + [EQ('home_visit', 'zero')])),
            DatabaseColumn(_('home_visits_newborn'),
                           CountColumn('doc_id', alias="home_visits_newborn",
                                       filters=self.filters + [OR([EQ('newborn_reg', 'one'),
                                                                   EQ('newborn_followup', 'one')])])),
            DatabaseColumn(_('home_visits_children'),
                           CountColumn('doc_id', alias="home_visits_children",
                                       filters=self.filters + [OR([EQ('child_reg', 'one'),
                                                                   EQ('child_followup', 'one')])])),
            DatabaseColumn(_('home_visits_followup'),
                           CountColumn('doc_id', alias="home_visits_followup",
                                       filters=self.filters + [OR([
                                           EQ('newborn_followup', 'one'),
                                           EQ('child_followup', 'one'),
                                           EQ('adult_followup', 'one')
                                       ])])),
            AggregateColumn(_("home_visits_total"), add_all, [
                AliasColumn("home_visits_pregnant"),
                AliasColumn("home_visits_non_pregnant"),
                AliasColumn("home_visits_newborn"),
                AliasColumn("home_visits_children"),
                AliasColumn("home_visits_followup"),
            ], slug='home_visits_total'),
            DatabaseColumn(_('deaths_children'),
                           CountColumn('doc_id', alias='deaths_children',
                                       filters=self.filters + [EQ('deaths_children', 'one')])),
            DatabaseColumn(_('patients_given_pneumonia_meds_num'),
                           CountColumn(
                               'doc_id',
                               alias='patients_given_pneumonia_meds_num',
                               filters=self.filters + [OR([
                                   AND([EQ('has_pneumonia', 'one'), EQ('it_ari_child', 'one')]),
                                   AND([EQ('pneumonia_ds', 'one'), EQ('it_ari_child', 'one')]),
                                   AND([EQ('ari_adult', 'one'), EQ('it_ari_adult', 'one')])])])),
            DatabaseColumn(_('patients_given_pneumonia_meds_denom'),
                           CountColumn(
                               'doc_id',
                               alias='patients_given_pneumonia_meds_denom',
                               filters=self.filters + [OR([
                                   EQ('has_pneumonia', 'one'),
                                   EQ('pneumonia_ds', 'one'),
                                   EQ('ari_adult', 'one')])])),
            AggregateColumn(_('patients_given_pneumonia_meds'), percent_format, [
                AliasColumn('patients_given_pneumonia_meds_num'),
                AliasColumn('patients_given_pneumonia_meds_denom')
            ], slug='patients_given_pneumonia_meds'),
            DatabaseColumn(_('patients_given_diarrhoea_meds_num'),
                           CountColumn(
                               'doc_id',
                               alias='patients_given_diarrhoea_meds_num',
                               filters=self.filters + [OR([
                                   AND([OR([EQ('diarrhoea_ds', 'one'), EQ('diarrhoea', 'one')]),
                                        EQ('it_diarrhea_child', 'one')]),
                                   AND([EQ('diarrhea_adult', 'one'), EQ('it_diarrhea_adult', 'one')])])])),
            DatabaseColumn(_('patients_given_diarrhoea_meds_denum'),
                           CountColumn(
                               'doc_id',
                               alias='patients_given_diarrhoea_meds_denum',
                               filters=self.filters + [OR([
                                   EQ('diarrhoea_ds', 'one'),
                                   EQ('diarrhoea', 'one'),
                                   EQ('diarrhea_adult', 'one')])])),
            AggregateColumn(_('patients_given_diarrhoea_meds'), percent_format, [
                AliasColumn('patients_given_diarrhoea_meds_num'),
                AliasColumn('patients_given_diarrhoea_meds_denum')
            ], slug='patients_given_diarrhoea_meds'),
            DatabaseColumn(_('patients_given_malaria_meds'),
                           CountColumn(
                               'doc_id',
                               alias='patients_given_malaria_meds_num',
                               filters=self.filters + [OR([
                                   AND([EQ('malaria_child', 'one'), EQ('it_malaria_child', 'one')]),
                                   AND([EQ('malaria_adult', 'one'), EQ('it_malaria_adult', 'one')])])])),
            DatabaseColumn(_('patients_given_malaria_meds_denum'),
                           CountColumn(
                               'doc_id',
                               alias='patients_given_malaria_meds_demum',
                               filters=self.filters + [OR([
                                   EQ('has_malaria', 'one'),
                                   EQ('malaria_adult', 'one')])])),
            AggregateColumn(_('patients_given_malaria_meds'), percent_format, [
                AliasColumn('patients_given_malaria_meds_num'),
                AliasColumn('patients_given_malaria_meds_demum')
            ], slug='patients_given_malaria_meds'),
            DatabaseColumn(_('patients_correctly_referred_num'),
                           CountColumn(
                               'doc_id',
                               alias='patients_correctly_referred_num',
                               filters=self.filters + [OR([
                                   AND([EQ('referral_needed_newborn', 'one'), EQ('referral_given_newborn', 'one')]),
                                   AND([EQ('referral_needed_child', 'one'), EQ('referral_given_child', 'one')]),
                                   AND([EQ('treatment_preg_ds', 'one'), EQ('referral_given_adult', 'one')])])])),
            DatabaseColumn(_('patients_correctly_referred_denum'),
                           CountColumn(
                               'doc_id',
                               alias='patients_correctly_referred_denum',
                               filters=self.filters + [OR([
                                   EQ('referral_needed_newborn', 'one'),
                                   EQ('referral_needed_child', 'one'),
                                   EQ('treatment_preg_ds', 'one')])])),
            AggregateColumn(_('patients_correctly_referred'), percent_format, [
                AliasColumn('patients_correctly_referred_num'),
                AliasColumn('patients_correctly_referred_denum')
            ], slug='patients_correctly_referred'),
            DatabaseColumn(_('cases_rdt_not_done'),
                           CountColumn('cases_rdt_not_done',
                                       filters=self.filters + [EQ('cases_rdt_not_done', 'one')])),
            DatabaseColumn(_('cases_danger_signs_not_referred'),
                           CountColumn('doc_id', alias='cases_danger_signs_not_referred',
                                       filters=self.filters + [OR([
                                           AND([EQ('internal_newborn_has_danger_sign', 'one'),
                                                EQ('referral_reported_newborn', 'zero')]),
                                           AND([EQ('internal_child_has_danger_sign', 'one'),
                                                EQ('internal_child_referral_not_given', 'one')]),
                                           AND([EQ('treatment_preg_ds', 'one'),
                                                EQ('internal_adult_referral_not_given', 'one')])
                                       ])])),
            DatabaseColumn(_('cases_no_malaria_meds'),
                           CountColumn('doc_id', alias='cases_no_malaria_meds',
                                       filters=self.filters + [OR([
                                           EQ('internal_child_no_malaria_meds', 'one'),
                                           EQ('internal_adult_no_malaria_meds', 'one')
                                       ])]))
        ]


class DistrictMonthly(BaseReport):
    fields = [
        'corehq.apps.reports.filters.dates.DatespanFilter',
        'custom.reports.mc.reports.fields.DistrictField',
    ]
    slug = 'district_monthly_ucr'
    name = "UCR Relatorio Mensal aos Coordinadores do Distrito e os NEDs"
    section = DISTRICT_MONTHLY_REPORT

    @property
    def columns(self):
        return [
            self.first_column,
            DatabaseColumn(_('home_visits_pregnant'),
                           CountColumn('home_visit', alias="home_visits_pregnant",
                                       filters=self.filters + [EQ('home_visit', 'one')])),
            DatabaseColumn(_('home_visits_postpartem'),
                           CountColumn('post_partem', alias="home_visits_postpartem",
                                       filters=self.filters + [EQ('post_partem', 'one')])),
            DatabaseColumn(_('home_visits_newborn'),
                           CountColumn('doc_id', alias="home_visits_newborn",
                                       filters=self.filters + [OR([EQ('newborn_reg', 'one'),
                                                                   EQ('newborn_followup', 'one')])])),
            DatabaseColumn(_('home_visits_children'),
                           CountColumn('doc_id', alias="home_visits_children",
                                       filters=self.filters + [OR([EQ('child_reg', 'one'),
                                                                   EQ('child_followup', 'one')])])),
            DatabaseColumn(_('home_visits_other'),
                           CountColumn('doc_id', alias="home_visits_other",
                                       filters=self.filters + [OR([
                                           AND([EQ('home_visit', 'zero'), EQ('post_partem', 'zero')]),
                                           EQ('sex', 'one'),
                                           EQ('adult_followup', 'one')])])),
            AggregateColumn(_("home_visits_total"), add_all, [
                AliasColumn("home_visits_pregnant"),
                AliasColumn("home_visits_postpartem"),
                AliasColumn("home_visits_newborn"),
                AliasColumn("home_visits_children"),
                AliasColumn("home_visits_other"),
            ], slug='home_visits_total'),
            DatabaseColumn(_('rdt_positive_children'),
                           CountColumn('doc_id', alias='rdt_positive_children',
                                       filters=self.filters + [EQ('rdt_children', 'one')])),
            DatabaseColumn(_('rdt_positive_adults'),
                           CountColumn('doc_id', alias='rdt_positive_adults',
                                       filters=self.filters + [EQ('rdt_adult', 'one')])),
            DatabaseColumn(_('rdt_others'),
                           CountColumn('doc_id', alias='rdt_others',
                                       filters=self.filters + [OR([EQ('rdt_adult', 'zero'),
                                                                   EQ('rdt_children', 'zero')])])),
            AggregateColumn(_('rdt_total'), add_all, [
                AliasColumn('rdt_positive_children'),
                AliasColumn('rdt_positive_adults'),
                AliasColumn('rdt_others')
            ], slug='rdt_total'),
            DatabaseColumn(_('diagnosed_malaria_child'),
                           CountColumn('malaria_child', alias='diagnosed_malaria_child',
                                       filters=self.filters + [EQ('malaria_child', 'one')])),
            DatabaseColumn(_('diagnosed_malaria_adult'),
                           CountColumn('malaria_adult', alias='diagnosed_malaria_adult',
                                       filters=self.filters + [EQ('malaria_adult', 'one')])),
            DatabaseColumn(_('diagnosed_diarrhea'),
                           CountColumn('doc_id', alias='diagnosed_diarrhea',
                                       filters=self.filters + [OR([
                                           EQ('diarrhea_child', 'one'),
                                           EQ('diarrhea_adult', 'one')
                                       ])])),
            DatabaseColumn(_('diagnosed_ari'),
                           CountColumn('doc_id', alias='diagnosed_ari',
                                       filters=self.filters + [OR([
                                           EQ('ari_child', 'one'),
                                           EQ('ari_adult', 'one')
                                       ])])),
            AggregateColumn(_('diagnosed_total'), add_all, [
                AliasColumn('diagnosed_malaria_child'),
                AliasColumn('diagnosed_malaria_adult'),
                AliasColumn('diagnosed_diarrhea'),
                AliasColumn('diagnosed_ari')
            ], slug='diagnosed_total'),
            DatabaseColumn(_('treated_malaria'),
                           CountColumn('doc_id', alias='treated_malaria', filters=self.filters + [OR([
                               AND([EQ('it_malaria_child', 'one'), EQ('malaria_child', 'one')]),
                               AND([EQ('it_malaria_adult', 'one'), EQ('malaria_adult', 'one')])
                           ])])),
            DatabaseColumn(_('treated_diarrhea'),
                           CountColumn('doc_id', alias='treated_diarrhea', filters=self.filters + [OR([
                               AND([EQ('diarrhea_child', 'one'), EQ('it_diarrhea_child', 'one')]),
                               AND([EQ('diarrhea_adult', 'one'), EQ('it_diarrhea_adult', 'one')])
                           ])])),
            DatabaseColumn(_('treated_ari'),
                           CountColumn('doc_id', alias='treated_ari', filters=self.filters + [OR([
                               AND([EQ('ari_child', 'one'), EQ('it_ari_child', 'one')]),
                               AND([EQ('ari_adult', 'one'), EQ('it_ari_adult', 'one')])
                           ])])),
            AggregateColumn(_('treated_total'), add_all, [
                AliasColumn('treated_malaria'),
                AliasColumn('treated_diarrhea'),
                AliasColumn('treated_ari')
            ], slug='treated_total'),
            DatabaseColumn(_('transfer_malnutrition'),
                           CountColumn('doc_id', alias='transfer_malnutrition', filters=self.filters + [OR([
                               EQ('malnutrition_child', 'one'),
                               EQ('malnutrition_adult', 'one')
                           ])])),
            DatabaseColumn(_('transfer_incomplete_vaccination'),
                           CountColumn('doc_id', alias='transfer_incomplete_vaccination',
                                       filters=self.filters + [OR([
                                           EQ('vaccination_child', 'one'),
                                           EQ('vaccination_adult', 'one'),
                                           EQ('vaccination_newborn', 'one')
                                       ])])),
            DatabaseColumn(_('transfer_danger_signs'),
                           CountColumn('doc_id', alias='transfer_danger_signs', filters=self.filters + [OR([
                               EQ('danger_sign_child', 'one'),
                               EQ('danger_sign_adult', 'one'),
                               EQ('danger_sign_newborn', 'one')
                           ])])),
            DatabaseColumn(_('transfer_prenatal_consult'),
                           CountColumn('doc_id', alias='transfer_prenatal_consult',
                                       filters=self.filters + [EQ('prenatal_consult', 'one')])),
            DatabaseColumn(_('transfer_missing_malaria_meds'),
                           CountColumn('doc_id', alias='transfer_missing_malaria_meds',
                                       filters=self.filters + [OR([
                                           EQ('missing_malaria_meds_child', 'one'),
                                           EQ('missing_malaria_meds_adult', 'one')
                                       ])])),
            DatabaseColumn(_('transfer_other'),
                           CountColumn('doc_id', alias='transfer_other', filters=self.filters + [OR([
                               EQ('other_child', 'one'),
                               EQ('other_adult', 'one'),
                               EQ('other_newborn', 'one')
                           ])])),
            AggregateColumn(_('transfer_total'), add_all, [
                AliasColumn('transfer_malnutrition'),
                AliasColumn('transfer_incomplete_vaccination'),
                AliasColumn('transfer_danger_signs'),
                AliasColumn('transfer_prenatal_consult'),
                AliasColumn('transfer_missing_malaria_meds'),
                AliasColumn('transfer_other'),
            ], slug='transfer_total'),
            DatabaseColumn(_('deaths_newborn'),
                           CountColumn('doc_id', alias='deaths_newborn',
                                       filters=self.filters + [EQ('deaths_newborn', 'one')])),
            DatabaseColumn(_('deaths_children'),
                           CountColumn('doc_id', alias='deaths_children',
                                       filters=self.filters + [EQ('deaths_children', 'one')])),
            DatabaseColumn(_('deaths_mothers'),
                           CountColumn('doc_id', alias='deaths_mothers',
                                       filters=self.filters + [EQ('deaths_mothers', 'one')])),
            DatabaseColumn(_('deaths_others'),
                           SumColumn('deaths_others', alias='deaths_other',
                                       filters=self.filters + [NOTEQ('deaths_others', 'zero')])),
            AggregateColumn(_('deaths_total'), add_all, [
                AliasColumn('deaths_newborn'),
                AliasColumn('deaths_children'),
                AliasColumn('deaths_mothers'),
                AliasColumn('deaths_other'),
            ], slug='deaths_total'),
            DatabaseColumn(_('heath_ed_talks'),
                           SumColumn('heath_ed_talks', alias='heath_ed_talks',
                                       filters=self.filters + [NOTEQ('heath_ed_talks', 'zero')])),
            DatabaseColumn(_('heath_ed_participants'),
                           SumColumn('heath_ed_participants', alias='heath_ed_participants',
                                     filters=self.filters + [NOTEQ('heath_ed_participants', 'zero')]))
        ]


class WeeklyForms(SqlData):

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], "weekly_forms")

    @property
    def engine_id(self):
        return 'ucr'

    @property
    def group_by(self):
        return [
            'date',
            'user_id',
            'hf',
            'district',
            'stock_amox_pink',
            'stock_amox_green',
            'stock_ors',
            'stock_ra_50',
            'stock_ra_200',
            'stock_zinc',
            'stock_coartem_yellow',
            'stock_coartem_blue',
            'stock_coartem_green',
            'stock_coartem_brown',
            'stock_paracetamol_250',
            'stock_paracetamol_500',
            'stock_rdt',
            'stock_gloves',
        ]

    @property
    def filters(self):
        filters = [BETWEEN('date', 'startdate', 'enddate'), NOTEQ('hf', 'empty')]
        if 'district' in self.config and self.config['district']:
            filters.append(EQ('district', 'district'))
        elif 'hf' in self.config and self.config['hf']:
            filters.append(EQ('hf', 'hf'))
        return filters

    @property
    def columns(self):
        return [
            DatabaseColumn('Date', SimpleColumn('date')),
            DatabaseColumn('user', SimpleColumn('user_id')),
            DatabaseColumn('hf', SimpleColumn('hf')),
            DatabaseColumn('district', SimpleColumn('district')),
            DatabaseColumn(_('form/stock/stock_amox_pink'), SimpleColumn('stock_amox_pink')),
            DatabaseColumn(_('form/stock/stock_amox_green'), SimpleColumn('stock_amox_green')),
            DatabaseColumn(_('form/stock/stock_ors'), SimpleColumn('stock_ors')),
            DatabaseColumn(_('form/stock/stock_ra_50'), SimpleColumn('stock_ra_50')),
            DatabaseColumn(_('form/stock/stock_ra_200'), SimpleColumn('stock_ra_200')),
            DatabaseColumn(_('form/stock/stock_zinc'), SimpleColumn('stock_zinc')),
            DatabaseColumn(_('form/stock/stock_coartem_yellow'), SimpleColumn('stock_coartem_yellow')),
            DatabaseColumn(_('form/stock/stock_coartem_blue'), SimpleColumn('stock_coartem_blue')),
            DatabaseColumn(_('form/stock/stock_coartem_green'), SimpleColumn('stock_coartem_green')),
            DatabaseColumn(_('form/stock/stock_coartem_brown'), SimpleColumn('stock_coartem_brown')),
            DatabaseColumn(_('form/stock/stock_paracetamol_250'), SimpleColumn('stock_paracetamol_250')),
            DatabaseColumn(_('form/stock/stock_paracetamol_500'), SimpleColumn('stock_paracetamol_500')),
            DatabaseColumn(_('form/stock/stock_rdt'), SimpleColumn('stock_rdt')),
            DatabaseColumn(_('form/stock/stock_gloves'), SimpleColumn('stock_gloves'))
        ]

    def get_data(self):
        data = super(WeeklyForms, self).get_data()
        last_submisions = {}
        for row in sorted(data, key=lambda x: x['date']):
            last_submisions.update({row['user_id']: row})
        weekly = {}
        def update_row(row1, row2):
            for key, value in row1.iteritems():
                if key not in ['date', 'user_id', 'hf', 'district']:
                    row2[key] += int(value)
        for user_data in last_submisions.values():
            if user_data['hf'] in weekly:
                update_row(user_data, weekly[user_data['hf']])
            else:
                weekly[user_data['hf']] = user_data
        return weekly


class HeathFacilityMonthly(DistrictMonthly):
    slug = 'hf_monthly_ucr'
    fields = [
        'corehq.apps.reports.filters.dates.DatespanFilter',
        'custom.reports.mc.reports.fields.HealthFacilityField',
    ]
    name = "UCR Relatorio Mensal aos Supervisores dos APEs"
    section = HF_MONTHLY_REPORT


class HealthFacilityWeekly(DistrictWeekly):
    report_template_path = "mc/reports/hf_weekly.html"
    extra_context_providers = [hf_message_content]
    fields = [
        'corehq.apps.reports.filters.dates.DatespanFilter',
        'custom.reports.mc.reports.fields.HealthFacilityField',
    ]
    slug = 'hf_weekly_ucr'
    #TODO change to ugettext when old reports remove
    name = "UCR Relatorio Semanal aos Supervisores dos APEs"
    section = HF_WEEKLY_REPORT

    @property
    def columns(self):
        return [
            self.first_column,
            DatabaseColumn(_('home_visits_newborn'),
                           CountColumn('doc_id', alias="home_visits_newborn",
                                       filters=self.filters + [OR([EQ('newborn_reg', 'one'),
                                                                   EQ('newborn_followup', 'one')])])),
            DatabaseColumn(_('home_visits_children'),
                           CountColumn('doc_id', alias="home_visits_children",
                                       filters=self.filters + [OR([EQ('child_reg', 'one'),
                                                                   EQ('child_followup', 'one')])])),
            DatabaseColumn(_('home_visits_adult'),
                           CountColumn('doc_id', alias="home_visits_adult",
                                       filters=self.filters + [NOTEQ('home_visit', 'not')])),
            AggregateColumn(_("home_visits_total"), add_all, [
                AliasColumn("home_visits_newborn"),
                AliasColumn("home_visits_children"),
                AliasColumn("home_visits_adult"),
            ], slug='home_visits_total'),
            DatabaseColumn(_('cases_transferred'),
                           CountColumn('doc_id', alias='cases_transferred',
                                       filters=self.filters + [OR([
                                           EQ('referral_reported_newborn', 'one'),
                                           EQ('referral_given_child', 'one'),
                                           EQ('referral_given_adult', 'one'),
                                       ])])),
            DatabaseColumn(_('home_visits_followup'),
                           CountColumn('doc_id', alias="home_visits_followup",
                                       filters=self.filters + [OR([
                                           EQ('newborn_followup', 'one'),
                                           EQ('child_followup', 'one'),
                                           EQ('adult_followup', 'one')
                                       ])])),
            DatabaseColumn(_('patients_given_pneumonia_meds_num'),
                           CountColumn(
                               'doc_id',
                               alias='patients_given_pneumonia_meds_num',
                               filters=self.filters + [OR([
                                   AND([EQ('has_pneumonia', 'one'), EQ('it_ari_child', 'one')]),
                                   AND([EQ('pneumonia_ds', 'one'), EQ('it_ari_child', 'one')]),
                                   AND([EQ('ari_adult', 'one'), EQ('it_ari_adult', 'one')])])])),
            DatabaseColumn(_('patients_given_pneumonia_meds_denom'),
                           CountColumn(
                               'doc_id',
                               alias='patients_given_pneumonia_meds_denom',
                               filters=self.filters + [OR([
                                   EQ('has_pneumonia', 'one'),
                                   EQ('pneumonia_ds', 'one'),
                                   EQ('ari_adult', 'one')])])),
            AggregateColumn(_('patients_given_pneumonia_meds'), percent_format, [
                AliasColumn('patients_given_pneumonia_meds_num'),
                AliasColumn('patients_given_pneumonia_meds_denom')
            ], slug='patients_given_pneumonia_meds'),
            DatabaseColumn(_('patients_given_diarrhoea_meds_num'),
                           CountColumn(
                               'doc_id',
                               alias='patients_given_diarrhoea_meds_num',
                               filters=self.filters + [OR([
                                   AND([OR([EQ('diarrhoea_ds', 'one'), EQ('diarrhoea', 'one')]),
                                        EQ('it_diarrhea_child', 'one')]),
                                   AND([EQ('diarrhea_adult', 'one'), EQ('it_diarrhea_adult', 'one')])])])),
            DatabaseColumn(_('patients_given_diarrhoea_meds_denum'),
                           CountColumn(
                               'doc_id',
                               alias='patients_given_diarrhoea_meds_denum',
                               filters=self.filters + [OR([
                                   EQ('diarrhoea_ds', 'one'),
                                   EQ('diarrhoea', 'one'),
                                   EQ('diarrhea_adult', 'one')])])),
            AggregateColumn(_('patients_given_diarrhoea_meds'), percent_format, [
                AliasColumn('patients_given_diarrhoea_meds_num'),
                AliasColumn('patients_given_diarrhoea_meds_denum')
            ], slug='patients_given_diarrhoea_meds'),
            DatabaseColumn(_('patients_given_malaria_meds'),
                           CountColumn(
                               'doc_id',
                               alias='patients_given_malaria_meds_num',
                               filters=self.filters + [OR([
                                   AND([EQ('malaria_child', 'one'), EQ('it_malaria_child', 'one')]),
                                   AND([EQ('malaria_adult', 'one'), EQ('it_malaria_adult', 'one')])])])),
            DatabaseColumn(_('patients_given_malaria_meds_denum'),
                           CountColumn(
                               'doc_id',
                               alias='patients_given_malaria_meds_demum',
                               filters=self.filters + [OR([
                                   EQ('has_malaria', 'one'),
                                   EQ('malaria_adult', 'one')])])),
            AggregateColumn(_('patients_given_malaria_meds'), percent_format, [
                AliasColumn('patients_given_malaria_meds_num'),
                AliasColumn('patients_given_malaria_meds_denum')
            ], slug='patients_given_malaria_meds'),
            DatabaseColumn(_('patients_correctly_referred_num'),
                           CountColumn(
                               'doc_id',
                               alias='patients_correctly_referred_num',
                               filters=self.filters + [OR([
                                   AND([EQ('referral_needed_newborn', 'one'), EQ('referral_given_newborn', 'one')]),
                                   AND([EQ('referral_needed_child', 'one'), EQ('referral_given_child', 'one')]),
                                   AND([EQ('treatment_preg_ds', 'one'), EQ('referral_given_adult', 'one')])])])),
            DatabaseColumn(_('patients_correctly_referred_denum'),
                           CountColumn(
                               'doc_id',
                               alias='patients_correctly_referred_denum',
                               filters=self.filters + [OR([
                                   EQ('referral_needed_newborn', 'one'),
                                   EQ('referral_needed_child', 'one'),
                                   EQ('treatment_preg_ds', 'one')])])),
            AggregateColumn(_('patients_correctly_referred'), percent_format, [
                AliasColumn('patients_correctly_referred_num'),
                AliasColumn('patients_correctly_referred_denum')
            ], slug='patients_correctly_referred'),
            DatabaseColumn(_('cases_rdt_not_done'),
                           CountColumn('cases_rdt_not_done',
                                       filters=self.filters + [EQ('cases_rdt_not_done', 'one')])),
        ]
