from sqlagg.columns import *
from corehq.apps.reports.sqlreport import SqlTabularReport, DatabaseColumn
from corehq.apps.reports.fields import AsyncDrillableField, GroupField, BooleanField
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.apps.users.models import CommCareUser
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DataTablesColumnGroup


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
        'custom.reports.care_sa.reports.sql.ProvinceField',
        'custom.reports.care_sa.reports.sql.CBOField',
        'custom.reports.care_sa.reports.sql.ShowAgeField',
        'custom.reports.care_sa.reports.sql.ShowGenderField',
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
        #if self.show_age():
        groups.append('age_group')
        #if self.show_gender():
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
    def headers(self):
        header_columns = []
        for idx, column in enumerate(self.columns):
            if idx >= (len(self.columns) - len(self.report_columns)) and self.show_gender():
                group = DataTablesColumnGroup(column.header)
                group.add_column(DataTablesColumn("male", sortable=False))
                group.add_column(DataTablesColumn("female", sortable=False))
                header_columns.append(group)
            else:
                # gender is a column for us to get data from but
                # we display this differently
                if column.header != 'Gender':
                    header_columns.append(DataTablesColumn(column.header))

        # insert a blank header to display the "all genders/ages" message
        if not self.show_gender() and not self.show_age():
            header_columns.insert(1, DataTablesColumn(''))

        return DataTablesHeader(*header_columns)

    @property
    def columns(self):
        user = DatabaseColumn("User", SimpleColumn('user_id'), sortable=False)
        columns = [user]

        if self.show_gender():
            columns.append(DatabaseColumn("Gender", SimpleColumn('gender'), sortable=False))
        if self.show_age():
            columns.append(DatabaseColumn("Age", SimpleColumn('age_group'), sortable=False))

        for column_attrs in self.report_columns:
            text, name = column_attrs[:2]
            name = '%s_total' % name
            if len(column_attrs) == 2:
                column = DatabaseColumn(text, SimpleColumn(name), sortable=False)
            elif column_attrs[2] == 'SumColumn':
                column = DatabaseColumn(text, SumColumn(name), sortable=False)

            columns.append(column)

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
            return ['--'] * len(self.report_columns)

    def add_row_to_total(self, total, row):
        # initialize it if it hasn't been used yet
        if len(total) == 0:
            total = [0] * len(row)

        return [a if isinstance(b, str) else a + b for (a, b) in zip(total, row)]

    def add_row_to_row(self, base_row, row_to_add):
        for i in range(len(base_row)):
            if isinstance(row_to_add[i], int):
                if isinstance(base_row[i], int):
                    base_row[i] = base_row[i] + row_to_add[i]
                else:
                    base_row[i] = row_to_add[i]

        return base_row

    def build_data(self, rows):
        built_data = {}

        for row in rows:
            try:
                user = CommCareUser.get_by_user_id(row.pop(0))
                u = user.username

                # TODO: we might not want to skip blank names
                if not user.name.strip():
                    continue
            except AttributeError:
                # TODO: figure out how often this happens and do something
                # better
                continue

            if u not in built_data:
                built_data[u] = self.initialize_user_stuff()

            if self.show_gender():
                gender = row.pop(0)

                #TODO skip?
                if gender == 'refuses_answer':
                    continue
            if self.show_age():
                age_group = row.pop(0)

                if age_group == 3:
                    continue

            if self.show_age() and self.show_gender():
                built_data[u][age_group][gender] = row
            elif self.show_age() and not self.show_gender():
                built_data[u][age_group] = self.add_row_to_row(built_data[u][age_group], row)
            elif not self.show_age() and self.show_gender():
                built_data[u][gender] = self.add_row_to_row(built_data[u][gender], row)
            elif not self.show_age() and not self.show_gender():
                built_data[u] = self.add_row_to_row(built_data[u], row)

        return built_data

    def age_group_text(self, age_group_val):
        if age_group_val == '0':
            return '0-14 years'
        elif age_group_val == '1':
            return '15-24 years'
        elif age_group_val == '2':
            return '25+ years'

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
                    if age_group == '3':
                        continue

                    age_display = self.age_group_text(age_group)

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

            elif self.show_age() and not self.show_gender():
                for age_group in sorted(rows[user]):
                    if age_group == '3':
                        continue

                    age_display = self.age_group_text(age_group)

                    row_data = rows[user][age_group]
                    rows_for_table.append({
                        'username': u.name if age_group == '0' else '',
                        'age_display': age_display,
                        'row_data': row_data
                    })

                    total_row = self.add_row_to_total(total_row, row_data)
            else:
                rows_for_table.append({
                    'username': u.name,
                    'gender':  'no_grouping',  # magic
                    'row_data': rows[user]
                })

            rows_for_table.append({
                'username': 'TOTAL_ROW',
                'total_width': 1 + int(self.show_age()),
                'gender': self.show_gender(),
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
        ['Individuals ref to PHCF with signs & symptoms of TB', 'referred_tb_signs'],  # 1f
        #retry['Newly diagnosed individuals HIV infected ref for CD4 count test in a PHCF', 'referred_for_cdf_new'],  # 1ha
        #retry['Existing patients HIV infected ref for CD4 count test in a PHCF', 'referred_for_cdf_existing'],  # 1hb
        ['Individuals HIV infected provided with CD4 count test results',
         'new_hiv_cd4_results'],  # 1i
        #RETRY['Individuals HIV infected provided with CD4 count test results from previous months',
        # 'new_hiv_in_care_program'],  # 1k
        ['People tested as individuals', 'individual_tests'],  # 1l
        ['People tested as couples', 'couple_tests', 'SumColumn'],  # 1m
        ['People tested at the community', 'hiv_community'],
    ]


class CareAndTBHIV(CareReport):
    slug = 'caretbhiv'
    name = "Care and TBHIV"

    report_columns = [
        ['Number of deceased patients', 'deceased'],  # 2a
        #['Number of patients lost to follow-up', TODO],  # 2b
        ['Patients completed TB treatment', 'tb_treatment_completed'],  # 2d
        ['All visits for CBC', 'received_cbc'],  # 2e
        ['Existing HIV+ individuals who received CBC', 'existing_cbc'],  # 2f
        ['New HIV+ individuals who received CBC', 'new_hiv_cbc'],  # 2g
        ['HIV infected patients newly started on IPT', 'new_hiv_starting_ipt'],  # 2h
        ['HIV infected patients newly receiving Bactrim', 'new_hiv_starting_bactrim'],  # 2i
        ['HIV+ patients receiving HIV care who are screened for symptoms of TB', 'hiv_on_care_screened_for_tb'],  # 2k
        ['Family members screened for symptoms of TB', 'family_screened', 'SumColumn'],  # 2l
    ]


class IACT(CareReport):
    slug = 'iact'
    name = 'I-ACT'

    report_columns = [
        ['HIV+ client enrolled for I-ACT', 'hiv_pos_enrolled'],  # 3a
        ['HIV+ client completed I-ACT', 'hiv_pos_completed'],  # 3b
        ['HIV+ clients registered for I-ACT & in the pipeline (5th session)', 'hiv_pos_pipeline'],  # 3c
        #['HIV+client registered for I-ACT after diagnosis', #TODO],  # 3d
        #retry['I-ACT participants receiving INH/IPT prophylaxis', 'iact_participant_ipt'],  # 3f
        #retry['I-ACT participants receiving Cotrimoxizole prophylaxis/Dapsone', 'iact_participant_ipt'],  # 3g
        #retry['I-ACT participant on Pre-ART', 'iact_participant_art'],  # 3h
        #retry['I-ACT participant on ARV', 'iact_participant_arv'],  # 3i
        #['I-ACT registered client with CD4 count <200', ''],  # 3j
        #['I-ACT registered client with CD4 count 200 - 350', ''],  # 3k
        #['I-ACT registered client with CD4 cont higher than 350', ''],  # 3l
        #['Unknown CD4 count at registration', ''],  # 3m
        #retry['I-ACT Support groups completed (all 6 sessions)', 'iact_support_groups'],  # 3n
    ]
