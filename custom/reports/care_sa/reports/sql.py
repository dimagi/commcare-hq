from sqlagg.columns import *
from corehq.apps.reports.sqlreport import SqlTabularReport, DatabaseColumn
from corehq.apps.reports.fields import AsyncDrillableField, GroupField, BooleanField
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.apps.users.models import CommCareUser
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DataTablesColumnGroup
from corehq.apps.fixtures.models import FixtureDataItem
from corehq.apps.groups.models import Group
from couchdbkit.exceptions import ResourceNotFound
from copy import copy


class ProvinceField(AsyncDrillableField):
    label = "Province"
    slug = "province"
    hierarchy = [{"type": "province", "display": "name"}]

class ShowAgeField(BooleanField):
    label = "Show Age"
    slug = "show_age_field"
    template = "care_sa/reports/partials/checkbox.html"

class ShowGenderField(BooleanField):
    label = "Show Gender"
    slug = "show_gender_field"
    template = "care_sa/reports/partials/checkbox.html"

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
        groups = []
        if not self.selected_province():
            groups.append('province')
        elif not self.selected_cbo():
            groups.append('cbo')
        else:
            groups.append('user_id')

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

    def first_indicator_column_index(self):
        return len(self.columns) - len(self.report_columns)

    @property
    def headers(self):
        """
        Override the headers method to be able to add male/female sub
        header columns.
        """
        header_columns = []
        for idx, column in enumerate(self.columns):
            if idx >= self.first_indicator_column_index() and self.show_gender():
                group = DataTablesColumnGroup(column.header)
                group.add_column(DataTablesColumn("male", sortable=False))
                group.add_column(DataTablesColumn("female", sortable=False))
                header_columns.append(group)
            else:
                # gender is included in the columns to populate data
                # but we don't show it on the page
                if column.header != 'Gender':
                    header_columns.append(DataTablesColumn(column.header, sortable=False))

        # insert a blank header to display the "all genders/ages" message
        if not self.show_gender() and not self.show_age():
            header_columns.insert(1, DataTablesColumn('', sortable=False))

        return DataTablesHeader(*header_columns)

    @property
    def columns(self):
        if not self.selected_province():
            columns = [DatabaseColumn("Province",
                                      SimpleColumn('province'),
                                      sortable=False)]
        elif not self.selected_cbo():
            columns = [DatabaseColumn("CBO",
                                      SimpleColumn('cbo'),
                                      sortable=False)]
        else:
            columns = [DatabaseColumn("User",
                                      SimpleColumn('user_id'),
                                      sortable=False)]

        if self.show_gender():
            columns.append(DatabaseColumn("Gender",
                                          SimpleColumn('gender'),
                                          sortable=False))
        if self.show_age():
            columns.append(DatabaseColumn("Age",
                                          SimpleColumn('age_group'),
                                          sortable=False))

        for column_attrs in self.report_columns:
            text, name = column_attrs[:2]
            name = '%s_total' % name
            if len(column_attrs) == 2:
                column = DatabaseColumn(text, CountColumn(name), sortable=False)
            elif column_attrs[2] == 'SumColumn':
                column = DatabaseColumn(text, SumColumn(name), sortable=False)

            columns.append(column)

        return columns

    @property
    def keys(self):
        [self.domain]

    @property
    def export_table(self):
        try:
            import xlwt
        except ImportError:
            raise Exception("It doesn't look like this machine is configured for "
                            "excel export. To export to excel you have to run the "
                            "command:  easy_install xlutils")

        headers = self.headers
        rows = self.rows
        formatted_rows = []
        for row in rows:
            if not self.show_age() and not self.show_gender():
                if 'total_width' not in row:
                    formatted_rows.append(
                        [row['username']] +
                        ['All genders and ages'] +
                        row['row_data']
                    )
            elif not self.show_age() and self.show_gender():
                if 'total_width' not in row:
                    formatted_rows.append(
                        [row['username']] +
                        row['row_data']
                    )
            else:
                # both groups with age get built the same
                if 'total_width' not in row:
                    formatted_rows.append(
                        [row['username']] +
                        [row['age_display']] +
                        row['row_data']
                    )
                else:
                    formatted_rows.append(
                        ['Total:', ''] +
                        row['row_data']
                    )


        def _unformat_row(row):
            return [col.get("sort_key", col) if isinstance(col, dict) else col for col in row]

        table = headers.as_table
        rows = [_unformat_row(row) for row in formatted_rows]
        table.extend(rows)
        if self.total_row:
            table.append(_unformat_row(self.total_row))
        if self.statistics_rows:
            table.extend([_unformat_row(row) for row in self.statistics_rows])

        return [[self.export_sheet_name, table]]

    def empty_row(self):
        return ['--'] * len(self.report_columns)

    def gender_seperated_dict(self):
        return {
            'male': self.empty_row(),
            'female': self.empty_row()
        }

    def age_seperated_dict(self, default):
        """ Build a dictionary with a copy of default for each age group """
        return dict((str(i), copy(default)) for i in range(4))

    def initialize_user_stuff(self):
        """
        Return a dictionary appropriately formatted based on the
        set filter options

        Used to seperate a given users/province/cbo's data into
        a dictionary seperated by age group and gender as
        needed
        """
        if self.show_age() and self.show_gender():
            return self.age_seperated_dict(self.gender_seperated_dict())

        if self.show_age() and not self.show_gender():
            return self.age_seperated_dict(self.empty_row())

        if not self.show_age() and self.show_gender():
            return self.gender_seperated_dict()

        if not self.show_age() and not self.show_gender():
            return self.empty_row()

    def add_row_to_total(self, total, row):
        # initialize it if it hasn't been used yet
        if len(total) == 0:
            total = [0] * len(row)

        return [a if isinstance(b, str) else a + b for (a, b) in zip(total, row)]

    def add_row_to_row(self, base_row, row_to_add):
        for i in range(len(base_row)):
            if isinstance(row_to_add[i], int) or isinstance(row_to_add[i], long):
                if isinstance(base_row[i], int):
                    base_row[i] = base_row[i] + int(row_to_add[i])
                else:
                    base_row[i] = row_to_add[i]

        return base_row

    def get_data_grouping_id(self, row):
        if not self.selected_province() or not self.selected_cbo():
            grouping_id = row.pop(0)
        else:
            # if it's a user we need to get the username
            user = CommCareUser.get_by_user_id(row.pop(0))
            grouping_id = user.username

        return grouping_id

    def add_row_to_grouping_data(self, built_data, row, grouping_id, age_group, gender):
        """
        Take whatever was left in row and add it to the appropriate spot in
        the data we are building for this grouping_id
        """
        if self.show_age() and self.show_gender():
            built_data[grouping_id][age_group][gender] = row
        elif self.show_age() and not self.show_gender():
            built_data[grouping_id][age_group] = \
                self.add_row_to_row(built_data[grouping_id][age_group], row)
        elif not self.show_age() and self.show_gender():
            built_data[grouping_id][gender] = \
                self.add_row_to_row(built_data[grouping_id][gender], row)
        elif not self.show_age() and not self.show_gender():
            built_data[grouping_id] = \
                self.add_row_to_row(built_data[grouping_id], row)

    def build_data(self, rows):
        """
        Take all of the individual data from the rows and collect it into
        a dict (built_data) that is used to group the values by gender/age
        """
        built_data = {}

        for row in rows:
            gender = age_group = None

            try:
                grouping_id = self.get_data_grouping_id(row)
            except AttributeError:
                continue

            if grouping_id not in built_data:
                # If we haven't seen this id yet we need to create
                # an empty row/dict (depending on selected filters)
                built_data[grouping_id] = self.initialize_user_stuff()

            if self.show_gender():
                gender = row.pop(0)
                if gender == 'refuses_answer':
                    continue

            if self.show_age():
                age_group = row.pop(0)

            self.add_row_to_grouping_data(
                built_data,
                row,
                grouping_id,
                age_group,
                gender
            )

        return built_data

    def age_group_text(self, age_group_val):
        if age_group_val == '0':
            return '0-14 years'
        elif age_group_val == '1':
            return '15-24 years'
        elif age_group_val == '2':
            return '25+ years'
        else:
            return 'Unknown'

    def get_grouping_name(self, user):
        """
        Get the name of province/cbo/user (depending on what is selected)
        """
        if not self.selected_province():
            return FixtureDataItem.get(user).fields_without_attributes['name']
        elif not self.selected_cbo():
            return Group.get(user).name
        else:
            return CommCareUser.get_by_username(user).name

    def merge_gender_data(self, data):
        return [val for pair in zip(data['male'], data['female'])
                for val in pair]

    @property
    def rows(self):
        """
        Override rows method to be able to properly group data
        """
        # use super to get the raw rows from the report
        stock_rows = list(super(CareReport, self).rows)

        # pack these rows into a dict representing the currently
        # configured report structure
        rows = self.build_data(stock_rows)

        # set up with for total rows
        if (not self.show_age() and self.show_gender()):
            total_width = 1
        else:
            total_width = 2

        rows_for_table = []
        overall_total_row = []
        age_group_totals = {'0': [], '1': [], '2': [], '3': []}

        # for every group of data, unpack back to individual rows
        # and set up the information the template needs to render this
        # stuff
        for user in rows:
            u = self.get_grouping_name(user)

            total_row = []
            if self.show_age() and self.show_gender():
                for age_group in sorted(rows[user]):
                    age_display = self.age_group_text(age_group)

                    row_data = self.merge_gender_data(rows[user][age_group])

                    rows_for_table.append({
                        'username': u if age_group == '0' else '',
                        'gender': True,
                        'age_display': age_display,
                        'row_data': row_data
                    })

                    age_group_totals[age_group] = self.add_row_to_total(
                        age_group_totals[age_group],
                        row_data
                    )

                    total_row = self.add_row_to_total(total_row, row_data)
            elif not self.show_age() and self.show_gender():
                row_data = self.merge_gender_data(rows[user])

                rows_for_table.append({
                    'username': u,
                    'gender': True,
                    'row_data': row_data
                })

            elif self.show_age() and not self.show_gender():
                for age_group in sorted(rows[user]):
                    row_data = rows[user][age_group]

                    rows_for_table.append({
                        'username': u if age_group == '0' else '',
                        'age_display': self.age_group_text(age_group),
                        'row_data': row_data
                    })

                    age_group_totals[age_group] = self.add_row_to_total(
                        age_group_totals[age_group],
                        row_data
                    )

                    total_row = self.add_row_to_total(total_row, row_data)
            else:
                row_data = rows[user]
                rows_for_table.append({
                    'username': u,
                    'gender':  'no_grouping',  # magic
                    'row_data': row_data
                })

            if total_row:
                overall_total_row = self.add_row_to_total(overall_total_row, total_row)
            else:
                # there is no total_row if we aren't grouping by age
                overall_total_row = self.add_row_to_total(overall_total_row, row_data)

            rows_for_table.append({
                'username': 'TOTAL_ROW',
                'total_width': total_width,
                'gender': self.show_gender(),
                'row_data': total_row,
            })

        if self.show_age():
            for group in ['0', '1', '2', '3']:
                rows_for_table.append({
                    'username': 'AGE_TOTAL_ROW',
                    'total_width': total_width,
                    'age_display': self.age_group_text(group),
                    'gender': self.show_gender(),
                    'row_data': age_group_totals[group]
                })

        rows_for_table.append({
            'username': 'OVERALL_TOTAL_ROW',
            'total_width': total_width,
            'gender': self.show_gender(),
            'row_data': overall_total_row,
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
        ['TB screening status known - TB Module', 'tb_screened'],  # 1ea
        ['TB screening status unknown - HCT Module', 'hct_screened'],  # 1eb
        ['Individuals ref to PHCF with signs & symptoms of TB', 'referred_tb_signs'],  # 1f
        ['Newly diagnosed individuals HIV infected ref for CD4 count test in a PHCF', 'referred_for_cdf_new'],  # 1ha TODO empty?
        ['Existing patients HIV infected ref for CD4 count test in a PHCF', 'referred_for_cdf_existing'],  # 1hb TODO empty?
        ['Individuals HIV infected provided with CD4 count test results',
         'new_hiv_cd4_results'],  # 1i
        ['Individuals HIV infected provided with CD4 count test results from previous months',
         'new_hiv_in_care_program'],  # 1k
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
        ['I-ACT participants receiving INH/IPT prophylaxis',
         'iact_participant_ipt'],  # 3f
        ['I-ACT participants receiving Cotrimoxizole prophylaxis/Dapsone',
         'iact_participant_bactrim'],  # 3g
        ['I-ACT participant on Pre-ART', 'iact_participant_art'],  # 3h
        ['I-ACT participant on ARV', 'iact_participant_arv'],  # 3i
        ['I-ACT registered client with CD4 count <200', 'cd4lt200'],  # 3j
        ['I-ACT registered client with CD4 count 200 - 350', 'cd4lt350'],  # 3k
        ['I-ACT registered client with CD4 cont higher than 350', 'cd4gt350'],  # 3l
        ['Unknown CD4 count at registration', 'unknown_cd4'],  # 3m
        ['I-ACT Support groups completed (all 6 sessions)', 'iact_support_groups'],  # 3n
    ]
