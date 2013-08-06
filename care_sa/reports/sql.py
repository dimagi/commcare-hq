from sqlagg.columns import *
from corehq.apps.reports.sqlreport import SqlTabularReport, DatabaseColumn
from corehq.apps.reports.fields import AsyncDrillableField, GroupField, BooleanField
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.apps.users.models import CommCareUser
from corehq.apps.reports.datatables import DataTablesColumnGroup


class ProvinceField(AsyncDrillableField):
    label = "Province"
    slug = "province"
    hierarchy = [{"type": "province", "display": "name"}]

class ShowAgeField(BooleanField):
    label = "Show Age"
    slug = "show_age_field"

class ShowGenderField(BooleanField):
    label = "Show Gender"
    slug = "show_gender_field"

class CBOField(GroupField):
    name = 'CBO'
    default_option = 'All'


class CareReport(SqlTabularReport,
                 CustomProjectReport,
                 DatespanMixin):
    exportable = True
    emailable = True
    table_name = "care-ihapc-live_CareSAFluff"
    report_template_path = "care_sa/reports/grouped.html"

    fields = [
        'corehq.apps.reports.fields.DatespanField',
        'care_sa.reports.sql.ProvinceField',
        'care_sa.reports.sql.CBOField',
        'care_sa.reports.sql.ShowAgeField',
        'care_sa.reports.sql.ShowGenderField',
    ]

    def selected_province(self):
        fixture = self.request.GET.get('fixture_id', "")
        return fixture.split(':')[1] if fixture else None

    def selected_cbo(self):
        group = self.request.GET.get('group', '')
        return group

    def show_age(self):
        show_age_field = self.request.GET.get('show_age_field', '')
        return show_age_field == 'on'

    def show_gender(self):
        show_gender_field = self.request.GET.get('show_gender_field', '')
        return show_gender_field == 'on'

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
        groups = ['user_id']
        if self.show_age():
            groups.append('age_group')
        if self.show_gender():
            groups.append('gender')

        return groups

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

        if not self.show_gender() and not self.show_age():
            # hack: we have to give it a column type so there are no errors
            # but this isn't a column we let be auto populated anyway
            columns.append(DatabaseColumn("", "gender", column_type=SimpleColumn))
        if self.show_gender():
            columns.append(DatabaseColumn("Gender", "gender", column_type=SimpleColumn))
        if self.show_age():
            columns.append(DatabaseColumn("Age", "age_group", column_type=SimpleColumn))

        for column_attrs in self.report_columns:
            text, name = column_attrs[:2]
            name = '%s_total' % name
            if len(column_attrs) == 2:
                group = DataTablesColumnGroup(text)
                column = DatabaseColumn(text, name, header_group=group)
                if self.show_gender():
                    column = DatabaseColumn('%s (male)' % text, name, header_group=group)
                    column2 = DatabaseColumn('%s (female)' % text, name, header_group=group, alias='%s_b' % name)
            else:
                # if there are more than 2 values, the third is the column
                # class override
                column = DatabaseColumn(text, name, column_attrs[2])
                if self.show_gender():
                    column = DatabaseColumn('%s (male)' % text, name, column_attrs[2])
                    column2 = DatabaseColumn('%s (female)' % text, name, header_group=group, alias='%s_b' % name)

            columns.append(column)
            # hacky but double the column if we are sorting by gender
            if self.show_gender():
                columns.append(column2)

        return columns

    @property
    def keys(self):
        [self.domain]

    def initialize_user_stuff(self):
        if self.show_age() and self.show_gender():
            return {
                '0': {
                    'male': ['--'] * len(self.report_columns),
                    'female': ['--'] * len(self.report_columns)
                },
                '1': {
                    'male': ['--'] * len(self.report_columns),
                    'female': ['--'] * len(self.report_columns)
                },
                '2': {
                    'male': ['--'] * len(self.report_columns),
                    'female': ['--'] * len(self.report_columns)
                }
            }
        if self.show_age() and not self.show_gender():
            return {
                '0': ['--'] * len(self.report_columns),
                '1': ['--'] * len(self.report_columns),
                '2': ['--'] * len(self.report_columns),
            }
        if not self.show_age() and self.show_gender():
            return {
                'male': ['--'] * len(self.report_columns),
                'female': ['--'] * len(self.report_columns)
            }
        if not self.show_age() and not self.show_gender():
            return len(self.report_columns),

    def build_data(self, rows):
        woot = {}

        for row in rows:
            try:
                u = CommCareUser.get_by_user_id(row.pop(0)['html']).username
            except AttributeError:
                # TODO: figure out how often this happens and do something
                # better
                continue

            if u not in woot:
                woot[u] = self.initialize_user_stuff()

            if self.show_gender():
                gender = row.pop(0)['html']

                #TODO skip?
                if gender == 'refuses_answer':
                    gender = 'male'
            if self.show_age():
                age_group = row.pop(0)['html']

            if not self.show_gender() and not self.show_age():
                # discard the gender column from blank header hack
                row.pop(0)

            # discard duplicates that exist if showing gender
            if self.show_gender():
                row = row[::2]

            # strip the dicts that come back for values
            row = [item['html'] if isinstance(item, dict) else item for item in row]

            if self.show_age() and self.show_gender():
                woot[u][age_group][gender] = row
            elif self.show_age() and not self.show_gender():
                woot[u][age_group] = row
            elif not self.show_age() and self.show_gender():
                woot[u][gender] = row
            elif not self.show_age() and not self.show_gender():
                woot[u] = row

        return woot

    def add_row_to_total(self, total, row):
        # initialize it if it hasn't been used yet
        if len(total) == 0:
            total = [0] * len(row)

        return [a if isinstance(b, str) else a + b for (a, b) in zip(total, row)]

    @property
    def rows(self):
        stock_rows = list(super(CareReport, self).rows)
        rows = self.build_data(stock_rows)

        rows_for_table = []
        for user in rows:
            u = CommCareUser.get_by_username(user)
            total_row = []
            if self.show_age() and self.show_gender():
                for age_group in sorted(rows[user]):

                    if age_group == '0':
                        age_display = '0-14 years'
                    elif age_group == '1':
                        age_display = '15-24 years'
                    else:
                        age_display = '25+ years'

                    row_data = [val for pair in zip(rows[user][age_group]['male'],
                                                    rows[user][age_group]['female'])
                                for val in pair]

                    rows_for_table.append({
                        'username': u.name if age_group == '0' else '',
                        'gender': True,
                        'age_display': age_display,
                        'row_data': row_data
                    })

                    total_row = self.add_row_to_total(total_row, row_data)
            elif not self.show_age() and self.show_gender():
                row_data = [val for pair in zip(rows[user]['male'],
                                                rows[user]['female'])
                            for val in pair]

                rows_for_table.append({
                    'username': u.name,
                    'gender': True,
                    'row_data': row_data
                })

                total_row = self.add_row_to_total([], row_data)
            elif self.show_age() and not self.show_gender():
                total_row = []
                for age_group in sorted(rows[user]):
                    u = CommCareUser.get_by_username(user)

                    if age_group == '0':
                        age_display = '0-14 years'
                    elif age_group == '1':
                        age_display = '15-24 years'
                    else:
                        age_display = '25+ years'

                    row_data = rows[user][age_group]
                    rows_for_table.append({
                        'username': u.name if age_group == '0' else '',
                        'age_display': age_display,
                        'row_data': row_data
                    })

                    total_row = self.add_row_to_total(total_row, row_data)
            else:
                u = CommCareUser.get_by_username(user)
                rows_for_table.append({
                    'username': u.name,
                    'gender':  'no_grouping',  # magic
                    'row_data': rows[user]
                })

            rows_for_table.append({
                'username': 'TOTAL_ROW',
                'gender': self.show_gender(),   # have to put data here to
                'age_display': self.show_age(), # reflect grouping status
                'row_data': total_row,
            })

        return rows_for_table

class TestingAndCounseling(CareReport):
    slug = 'tac'
    name = "Testing and Counseling"

    report_columns = [
        ['HIV Counseling', 'hiv_counseling'],
        ['Individuals HIV tested', 'hiv_tested'],
        ['Individuals HIV Positive ', 'hiv_positive'],
        ['Newly diagnosed HIV+ indv scr for TB', 'new_hiv_tb_screen'],  # 1d
        ['Individuals scr for TB [status unknown]', 'hiv_known_screened'],  # 1e
        #TODO NO DATA ['Individuals ref to PHCF with signs & symptoms of TB', 'referred_tb_signs'],  # 1f
        #['Individuals ref for TB diagnosis to PHCF who receive results', 'TODO'],  # 1g
        #TODO NO DATA ['Individuals HIV infected ref for CD4 count test in a PHCF', 'referred_for_cdf_new'],  # 1h
        ['Individuals HIV infected provided with CD4 count test results',
         'new_hiv_cd4_results'],  # 1i
        #TODO NO DATA ['Individuals HIV infected provided with CD4 count test results from previous months',
        # 'new_hiv_in_care_program'],  # 1k
        ['People tested as individuals', 'individual_tests'],  # 1l
        ['People tested as couples', 'couple_tests', SumColumn],  # 1m
    ]


class CareAndTBHIV(CareReport):
    slug = 'caretbhiv'
    name = "Care and TBHIV"

    report_columns = [
        ['Number of deceased patients', 'deceased'],  # 2a
        #['Number of patients lost to follow-up', TODO],  # 2b
        #not in form['Patients discharged from the program',  # 2c
        ['Patients completed TB treatment', 'tb_treatment_completed'],  # 2d
        #TODO NO DATA ['Existing HIV+ individuals who received CBC', 'received_cbc'],  # 2e
        #['New HIV+ individuals who received CBC', TODO],  # 2f
        # 2g
        ['HIV infected patients newly started on IPT', 'new_hiv_starting_ipt'],  # 2h
        ['HIV infected patients newly receiving Bactrim', 'new_hiv_starting_bactrim'],  # 2i
        #not in form['Clinically malnourished patients newly received therapeutic or supl food',  # 2j
        ['HIV+ patients receiving HIV care who are screened for symptoms of TB', 'hiv_on_care_screened_for_tb'],  # 2k
        ['Family members screened for symptoms of TB', 'family_screened'],  # 2l
    ]
