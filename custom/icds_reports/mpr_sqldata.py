from operator import mul, div, sub

from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DataTablesColumnGroup

from django.utils.translation import ugettext as _

from custom.icds_reports.sqldata import BaseIdentification, BaseOperationalization, BasePopulation
from custom.icds_reports.utils import ICDSMixin, MPRData, ICDSDataTableColumn


class MPRIdentification(BaseIdentification):

    @property
    def rows(self):
        if self.config['location_id']:
            chosen_location = SQLLocation.objects.get(
                location_id=self.config['location_id']
            ).get_ancestors(include_self=True)
            rows = []
            for loc_type in ['State', 'District', 'Block']:
                loc = chosen_location.filter(location_type__name=loc_type.lower())
                if len(loc) == 1:
                    rows.append([loc_type, loc[0].name, loc[0].site_code])
                else:
                    rows.append([loc_type, '', ''])
            return rows


class MPROperationalization(BaseOperationalization, MPRData):
    pass


class MPRSectors(object):

    title = 'd. No of Sectors'
    slug = 'sectors'
    has_sections = False
    subtitle = []
    posttitle = None

    def __init__(self, config):
        self.config = config

    @property
    def headers(self):
        return []

    @property
    def rows(self):
        if self.config['location_id']:
            selected_location = SQLLocation.objects.get(
                location_id=self.config['location_id']
            )
            supervisors = selected_location.get_descendants(include_self=True).filter(
                location_type__name='supervisor'
            )
            sup_number = [
                loc for loc in supervisors
                if 'test' not in loc.metadata and loc.metadata.get('test', '').lower() != 'yes'
            ]
            return [
                [
                    "Number of Sectors",
                    len(sup_number)
                ]
            ]


class MPRPopulation(BasePopulation, MPRData):

    title = 'e. Total Population of Project'


class MPRBirthsAndDeaths(ICDSMixin, MPRData):

    title = '2. Details of Births and Deaths during the month'
    slug = 'births_and_deaths'

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_('Si No')),
            DataTablesColumn(_('Categories')),
            DataTablesColumnGroup(
                _('Among Permanent Residents'),
                ICDSDataTableColumn(_('Girls/Women'), sortable=False, span=1),
                ICDSDataTableColumn(_('Boys'), sortable=False, span=1),
            ),
            DataTablesColumnGroup(
                _('Among Permanent Residents'),
                ICDSDataTableColumn(_('Girls/Women'), sortable=False, span=1),
                ICDSDataTableColumn(_('Boys'), sortable=False, span=1),
            )
        )

    @property
    def rows(self):
        if self.config['location_id']:
            data = self.custom_data(selected_location=self.selected_location, domain=self.config['domain'])
            rows = []
            for row in self.row_config:
                row_data = []
                for idx, cell in enumerate(row):
                    if isinstance(cell, tuple):
                        x = data.get(cell[0], 0)
                        y = data.get(cell[1], 0)
                        row_data.append(x + y)
                    else:
                        row_data.append(data.get(cell, cell if cell == '--' or idx in [0, 1] else 0))
                rows.append(row_data)
            return rows

    @property
    def row_config(self):
        return (
            (
                _('A'),
                _('No. of live births'),
                'live_F_resident_birth_count',
                'live_M_resident_birth_count',
                'live_F_migrant_birth_count',
                'live_M_migrant_birth_count'
            ),
            (
                _('B'),
                _('No. of babies born dead'),
                'still_F_resident_birth_count',
                'still_M_resident_birth_count',
                'still_F_migrant_birth_count',
                'still_M_migrant_birth_count'
            ),
            (
                _('C'),
                _('No. of babies weighed within 3 days of birth'),
                'weighed_F_resident_birth_count',
                'weighed_M_resident_birth_count',
                'weighed_F_migrant_birth_count',
                'weighed_M_migrant_birth_count'
            ),
            (
                _('D'),
                _('Out of the above, no. of low birth weight babies (< 2500 gm)'),
                'lbw_F_resident_birth_count',
                'lbw_M_resident_birth_count',
                'lbw_F_migrant_birth_count',
                'lbw_M_migrant_birth_count'
            ),
            (
                _('E'),
                _('No. of neonatal deaths (within 28 days of birth)'),
                'dead_F_resident_neo_count',
                'dead_M_resident_neo_count',
                'dead_F_migrant_neo_count',
                'dead_M_migrant_neo_count'
            ),
            (
                _('F'),
                _('No. of post neonatal deaths (between 29 days and 12 months of birth)'),
                'dead_F_resident_postneo_count',
                'dead_M_resident_postneo_count',
                'dead_F_migrant_postneo_count',
                'dead_M_migrant_postneo_count'
            ),
            (
                _('G'),
                _('Total infant deaths (E+F)'),
                ('dead_F_resident_neo_count', 'dead_F_resident_postneo_count'),
                ('dead_M_resident_neo_count', 'dead_M_resident_postneo_count'),
                ('dead_F_migrant_neo_count', 'dead_F_migrant_postneo_count'),
                ('dead_M_migrant_neo_count', 'dead_M_migrant_postneo_count'),
            ),
            (
                _('H'),
                _('Total child deaths (1- 5 years)'),
                'dead_F_resident_child_count',
                'dead_M_resident_child_count',
                'dead_F_migrant_child_count',
                'dead_M_migrant_child_count'
            ),
            (
                _('I'),
                _('No. of deaths of women'),
                'dead_F_resident_adult_count',
                '--',
                'dead_F_migrant_adult_count',
                '--'
            ),
            (
                '',
                _('a. during pregnancy'),
                'dead_preg_resident_count',
                '--',
                'dead_preg_migrant_count',
                '--'
            ),
            (
                '',
                _('b. during delivery'),
                'dead_del_resident_count',
                '--',
                'dead_del_migrant_count',
                '--'
            ),
            (
                '',
                _('c. within 42 days of delivery'),
                'dead_pnc_resident_count',
                '--',
                'dead_pnc_migrant_count',
                '--',
            ),
        )


class MPRAWCDetails(ICDSMixin, MPRData):

    title = '3. Details of new registrations at AWC during the month'
    slug = 'awc_details'

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_('Category')),
            DataTablesColumnGroup(
                _('Among permanent residents of AWC area'),
                ICDSDataTableColumn(_('Girls/Women'), sortable=False, span=1),
                ICDSDataTableColumn(_('Boys'), sortable=False, span=1),
            ),
            DataTablesColumnGroup(
                _('Among temporary residents of AWC area'),
                ICDSDataTableColumn(_('Girls/Women'), sortable=False, span=1),
                ICDSDataTableColumn(_('Boys'), sortable=False, span=1),
            )
        )

    @property
    def rows(self):
        if self.config['location_id']:
            data = self.custom_data(selected_location=self.selected_location, domain=self.config['domain'])
            rows = []
            for row in self.row_config:
                row_data = []
                for idx, cell in enumerate(row):
                    row_data.append(data.get(cell, cell if cell == '--' or idx == 0 else 0))
                rows.append(row_data)
            return rows

    @property
    def row_config(self):
        return (
            (
                _('a. Pregnant Women'),
                'pregnant_resident_count',
                '--',
                'pregnant_migrant_count',
                '--'
            ),
            (
                _('b. Live Births'),
                'live_F_resident_birth_count',
                'live_M_resident_birth_count',
                'live_F_migrant_birth_count',
                'live_M_migrant_birth_count'
            ),
            (
                _('c. 0-3 years children (excluding live births)'),
                'F_resident_count',
                'M_resident_count',
                'F_migrant_count',
                'M_migrant_count'
            ),
            (
                _('d. 3-6 years children'),
                'F_resident_count_1',
                'M_resident_count_1',
                'F_migrant_count_1',
                'M_migrant_count_1'
            ),
        )


class MPRSupplementaryNutrition(ICDSMixin, MPRData):

    title = '4. Delivery of Supplementary Nutrition and Pre-School Education (PSE)'
    slug = 'supplementary_nutrition'

    def __init__(self, config):
        super(MPRSupplementaryNutrition, self).__init__(config)
        self.awc_open_count = 0

    @property
    def subtitle(self):
        return 'Average no. days AWCs were open during the month? %.1f' % div(
            self.awc_open_count, float(self.awc_number or 1)
        ),

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(''),
            DataTablesColumn(_('Morning snacks/ breakfast')),
            DataTablesColumn(_('Hot cooked meals/RTE')),
            DataTablesColumn(_('Take home ration (THR')),
            DataTablesColumn(_('PSE'))
        )

    @property
    def rows(self):
        if self.config['location_id']:
            data = self.custom_data(selected_location=self.selected_location, domain=self.config['domain'])
            self.awc_open_count = data.get('awc_open_count', 0)
            rows = []
            for row in self.row_config:
                row_data = []
                for idx, cell in enumerate(row):
                    if isinstance(cell, dict):
                        num = data.get(cell['column'], 0)
                        if cell['second_value'] == 'location_number':
                            denom = self.awc_number
                        else:
                            denom = data.get(cell['second_value'], 1)
                        if 'format' in cell:
                            cell_data = '%.1f%%' % (cell['func'](num, float(denom or 1)) * 100)
                        else:
                            cell_data = '%.1f' % cell['func'](num, float(denom or 1))
                        row_data.append(cell_data)
                    else:
                        row_data.append(data.get(cell, cell if cell == '--' or idx == 0 else 0))
                rows.append(row_data)
            return rows

    @property
    def row_config(self):
        return (
            (
                _('a. Average number of days services were provided'),
                {
                    'column': 'open_bfast_count',
                    'func': div,
                    'second_value': "location_number",
                },
                {
                    'column': 'open_hotcooked_count',
                    'func': div,
                    'second_value': "location_number",
                },
                {
                    'column': 'days_thr_provided_count',
                    'func': div,
                    'second_value': "location_number",
                },
                {
                    'column': 'open_pse_count',
                    'func': div,
                    'second_value': "location_number",
                }
            ),
            (
                _('b. % of AWCs provided supplementary food for 21 or more days'),
                {
                    'column': 'open_bfast_count_21',
                    'func': div,
                    'second_value': "location_number",
                    'format': 'percent'
                },
                {
                    'column': 'open_hotcooked_count_21',
                    'func': div,
                    'second_value': "location_number",
                    'format': 'percent'
                },
                '--',
                '--'
            ),
            (
                _('c. % of AWCs providing PSE for 16 or more days'),
                '--',
                '--',
                '--',
                {
                    'column': 'open_hotcooked_count_16',
                    'func': div,
                    'second_value': "location_number",
                    'format': 'percent'
                }
            ),
            (
                _('d. % of AWCs providing services for 9 days or less'),
                {
                    'column': 'open_bfast_count_9',
                    'func': div,
                    'second_value': "location_number",
                    'format': 'percent'
                },
                {
                    'column': 'open_hotcooked_count_9',
                    'func': div,
                    'second_value': "location_number",
                    'format': 'percent'
                },
                '',
                {
                    'column': 'open_hotcooked_count_9',
                    'func': div,
                    'second_value': "location_number",
                    'format': 'percent'
                }
            ),
        )


class MPRUsingSalt(ICDSMixin, MPRData):

    slug = 'using_salt'

    @property
    def title(self):
        if self.config['location_id']:
            data = self.custom_data(selected_location=self.selected_location, domain=self.config['domain'])
            use_salt = data.get('use_salt', 0)

            return "5. Number of AWCs using Iodized Salt: {0}  % of AWCs: {0}/{1}".format(
                use_salt,
                self.awc_number
            )


class MPRProgrammeCoverage(ICDSMixin, MPRData):

    title = '6. Programme Coverage'
    slug = 'programme_coverage'
    has_sections = True

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('Category'),
            DataTablesColumnGroup(
                _('6-35 months'),
                DataTablesColumn(_('Girls')),
                DataTablesColumn(_('Boys'))
            ),
            DataTablesColumnGroup(
                _('3-71 months'),
                DataTablesColumn(_('Girls')),
                DataTablesColumn(_('Boys'))
            ),
            DataTablesColumnGroup(
                _('All Children (6-71 months)'),
                DataTablesColumn(_('Girls')),
                DataTablesColumn(_('Boys')),
                DataTablesColumn(_('Total'))
            ),
            DataTablesColumn(_('Pregnant Women')),
            DataTablesColumn(_('Lactating mothers'))
        )

    @property
    def rows(self):
        if self.config['location_id']:
            data = self.custom_data(selected_location=self.selected_location, domain=self.config['domain'])
            sections = []
            for section in self.row_config:
                rows = []
                for row in section['rows_config']:
                    row_data = []
                    for idx, cell in enumerate(row):
                        if isinstance(cell, dict):
                            num = 0
                            for c in cell['columns']:
                                num += data.get(c, 0)

                            if 'second_value' in cell:
                                denom = data.get(cell['second_value'], 1)
                                alias_data = cell['func'](num, float(denom or 1))
                                if "format" in cell:
                                    cell_data = "%.1f%%" % (cell['func'](num, float(denom or 1)) * 100)
                                else:
                                    cell_data = "%.1f" % cell['func'](num, float(denom or 1))
                            else:
                                cell_data = num
                                alias_data = num

                            if 'alias' in cell:
                                data[cell['alias']] = alias_data
                            row_data.append(cell_data)
                        elif isinstance(cell, tuple):
                            cell_data = 0
                            for c in cell:
                                cell_data += data.get(c, 0)
                            row_data.append(cell_data)
                        else:
                            row_data.append(data.get(cell, cell if cell == '--' or idx == 0 else 0))
                    rows.append(row_data)
                sections.append(dict(
                    title=section['title'],
                    headers=self.headers,
                    slug=section['slug'],
                    rows=rows
                ))
            return sections

    @property
    def row_config(self):
        return [
            {
                'title': "a. Supplementary Nutrition beneficiaries (number of those among "
                         "residents who were given supplementary nutrition for 21+ days "
                         "during the reporting month)",
                'slug': 'programme_coverage_1',
                'rows_config': (
                    (
                        _('ST'),
                        'thr_rations_female_st',
                        'thr_rations_male_st',
                        'thr_rations_female_st_1',
                        'thr_rations_male_st_1',
                        {
                            'columns': ('thr_rations_female_st', 'thr_rations_female_st_1'),
                            'alias': 'rations_female_st'
                        },
                        {
                            'columns': ('thr_rations_male_st', 'thr_rations_male_st_1'),
                            'alias': 'rations_male_st'
                        },
                        {
                            'columns': ('rations_female_st', 'rations_male_st'),
                            'alias': 'all_rations_st'
                        },
                        'thr_rations_pregnant_st',
                        'thr_rations_lactating_st'
                    ),
                    (
                        _('SC'),
                        'thr_rations_female_sc',
                        'thr_rations_male_sc',
                        'thr_rations_female_sc_1',
                        'thr_rations_male_sc_1',
                        {
                            'columns': ('thr_rations_female_sc', 'thr_rations_female_sc_1'),
                            'alias': 'rations_female_sc'
                        },
                        {
                            'columns': ('thr_rations_male_sc', 'thr_rations_male_sc_1'),
                            'alias': 'rations_male_sc'
                        },
                        {
                            'columns': ('rations_female_sc', 'rations_male_sc'),
                            'alias': 'all_rations_sc'
                        },
                        'thr_rations_pregnant_sc',
                        'thr_rations_lactating_sc'
                    ),
                    (
                        _('Other'),
                        'thr_rations_female_other',
                        'thr_rations_male_other',
                        'thr_rations_female_other_1',
                        'thr_rations_male_other_1',
                        {
                            'columns': ('thr_rations_female_other', 'thr_rations_female_other_1'),
                            'alias': 'rations_female_other'
                        },
                        {
                            'columns': ('thr_rations_male_other', 'thr_rations_male_other_1'),
                            'alias': 'rations_male_other'
                        },
                        {
                            'columns': ('rations_female_other', 'rations_male_other'),
                            'alias': 'all_rations_other'
                        },
                        'thr_rations_pregnant_other',
                        'thr_rations_lactating_other'
                    ),
                    (
                        _('All Categories (Total)'),
                        ('thr_rations_female_st', 'thr_rations_female_sc', 'thr_rations_female_other'),
                        ('thr_rations_male_st', 'thr_rations_male_sc', 'thr_rations_male_other'),
                        ('thr_rations_female_st_1', 'thr_rations_female_sc_1', 'thr_rations_female_other_1'),
                        ('thr_rations_male_st_1', 'thr_rations_male_sc_1', 'thr_rations_male_other_1'),
                        ('rations_female_st', 'rations_female_sc', 'rations_female_other'),
                        ('rations_male_st', 'rations_male_sc', 'rations_male_other'),
                        ('all_rations_st' 'all_rations_sc', 'all_rations_other'),
                        ('thr_rations_pregnant_st', 'thr_rations_pregnant_sc', 'thr_rations_pregnant_other'),
                        ('thr_rations_lactating_st', 'thr_rations_lactating_sc', 'thr_rations_lactating_other'),
                    ),
                    (
                        _('Disabled'),
                        'thr_rations_female_disabled',
                        'thr_rations_male_disabled',
                        'thr_rations_female_disabled_1',
                        'thr_rations_male_disabled_1',
                        ('thr_rations_female_disabled', 'thr_rations_female_disabled_1'),
                        ('thr_rations_male_disabled', 'thr_rations_male_disabled_1'),
                        ('thr_rations_female_disabled', 'thr_rations_female_disabled_1',
                         'thr_rations_male_disabled', 'thr_rations_male_disabled_1'),
                        'thr_rations_pregnant_disabled',
                        'thr_rations_lactating_disabled'
                    ),
                    (
                        _('Minority'),
                        'thr_rations_female_minority',
                        'thr_rations_male_minority',
                        'thr_rations_female_minority_1',
                        'thr_rations_male_minority_1',
                        ('thr_rations_female_minority', 'thr_rations_female_minority_1'),
                        ('thr_rations_male_minority', 'thr_rations_male_minority_1'),
                        ('thr_rations_female_minority', 'thr_rations_female_minority_1',
                         'thr_rations_male_minority', 'thr_rations_male_minority_1'),
                        'thr_rations_pregnant_minority',
                        'thr_rations_lactating_minority'
                    ),
                )
            },
            {
                'title': 'b. Feeding Efficiency',
                'slug': 'programme_coverage_2',
                'rows_config': (
                    (
                        _('I. Population Total'),
                        'child_count_female',
                        'child_count_male',
                        'child_count_female_1',
                        'child_count_male_1',
                        ('child_count_female', 'child_count_female_1'),
                        ('child_count_male', 'child_count_male_1'),
                        ('child_count_female', 'child_count_female_1',
                         'child_count_male', 'child_count_male_1'),
                        'pregnant',
                        'lactating'
                    ),
                    (
                        _('II. Usual absentees during the month'),
                        'thr_rations_absent_female',
                        'thr_rations_absent_male',
                        'thr_rations_absent_female_1',
                        'thr_rations_absent_male_1',
                        ('thr_rations_absent_female', 'thr_rations_absent_female_1'),
                        ('thr_rations_absent_male', 'thr_rations_absent_male_1'),
                        ('thr_rations_absent_female', 'thr_rations_absent_female_1',
                         'thr_rations_absent_male', 'thr_rations_absent_male_1'),
                        'thr_rations_absent_pregnant',
                        'thr_rations_absent_lactating'
                    ),
                    (
                        _('III. Total present for at least one day during the month'),
                        'thr_rations_partial_female',
                        'thr_rations_partial_male',
                        'thr_rations_partial_female_1',
                        'thr_rations_partial_male_1',
                        {
                            'columns': ('thr_rations_partial_female', 'thr_rations_partial_female_1'),
                            'alias': 'total_rations_partial_female',
                        },
                        {
                            'columns': ('thr_rations_partial_male', 'thr_rations_partial_male_1'),
                            'alias': 'total_rations_partial_male'
                        },
                        {
                            'columns': ('total_rations_partial_female', 'total_rations_partial_male'),
                            'alias': 'all_rations_partial'
                        },
                        'thr_rations_partial_pregnant',
                        'thr_rations_partial_lactating'
                    ),
                    (
                        _('IV. Expected Total Person Feeding Days (TPFD)'),
                        {
                            'columns': ('thr_rations_partial_female',),
                            'func': mul,
                            'second_value': 'days_thr_provided_count',
                            'alias': 'rations_partial_female'
                        },
                        {
                            'columns': ('thr_rations_partial_male',),
                            'func': mul,
                            'second_value': 'days_thr_provided_count',
                            'alias': 'rations_partial_male'
                        },
                        {
                            'columns': ('thr_rations_partial_female_1',),
                            'func': mul,
                            'second_value': 'days_thr_provided_count',
                            'alias': 'rations_partial_female_1'
                        },
                        {
                            'columns': ('thr_rations_partial_male_1',),
                            'func': mul,
                            'second_value': 'days_thr_provided_count',
                            'alias': 'rations_partial_female_1'
                        },
                        {
                            'columns': ('total_rations_partial_female',),
                            'func': mul,
                            'second_value': 'days_thr_provided_count',
                            'alias': 'all_rations_partial_female'
                        },
                        {
                            'columns': ('total_rations_partial_male',),
                            'func': mul,
                            'second_value': 'days_thr_provided_count',
                            'alias': 'all_rations_partial_male'
                        },
                        {
                            'columns': ('all_rations_partial',),
                            'func': mul,
                            'second_value': 'days_thr_provided_count',
                            'alias': 'rations_partial'
                        },
                        {
                            'columns': ('thr_rations_partial_pregnant',),
                            'func': mul,
                            'second_value': 'days_thr_provided_count',
                            'alias': 'rations_partial_pregnant'
                        },
                        {
                            'columns': ('thr_rations_partial_lactating',),
                            'func': mul,
                            'second_value': 'days_thr_provided_count',
                            'alias': 'rations_partial_lactating'
                        }
                    ),
                    (
                        _('V. Actual TPFD'),
                        'thr_total_rations_female',
                        'thr_total_rations_male',
                        'thr_total_rations_female_1',
                        'thr_total_rations_male_1',
                        {
                            'columns': ('thr_total_rations_female', 'thr_total_rations_female_1'),
                            'alias': 'total_thr_total_rations_female'
                        },
                        {
                            'columns': ('thr_total_rations_male', 'thr_total_rations_male_1'),
                            'alias': 'total_thr_total_rations_male'
                        },
                        {
                            'columns': ('total_thr_total_rations_female', 'total_thr_total_rations_male'),
                            'alias': 'total_thr_total_rations'
                        },
                        'thr_rations_pregnant_minority',
                        'thr_rations_lactating_minority'
                    ),
                    (
                        _('VI. Feeding Efficiency'),
                        {
                            'columns': ('thr_total_rations_female',),
                            'func': div,
                            'second_value': 'rations_partial_female',
                        },
                        {
                            'columns': ('thr_total_rations_male',),
                            'func': div,
                            'second_value': 'rations_partial_male',
                        },
                        {
                            'columns': ('thr_total_rations_female_1',),
                            'func': div,
                            'second_value': 'rations_partial_female_1',
                        },
                        {
                            'columns': ('thr_total_rations_male_1',),
                            'func': div,
                            'second_value': 'rations_partial_male_1',
                        },
                        {
                            'columns': ('total_thr_total_rations_female',),
                            'func': div,
                            'second_value': 'all_rations_partial_female',
                        },
                        {
                            'columns': ('total_thr_total_rations_male',),
                            'func': div,
                            'second_value': 'all_rations_partial_male',
                        },
                        {
                            'columns': ('total_thr_total_rations',),
                            'func': div,
                            'second_value': 'rations_partial',
                        },
                        {
                            'columns': ('thr_rations_pregnant_minority',),
                            'func': div,
                            'second_value': 'rations_partial_pregnant',
                        },
                        {
                            'columns': ('thr_rations_lactating_minority',),
                            'func': div,
                            'second_value': 'rations_partial_lactating',
                        },
                    ),
                )
            },
            {
                'title': 'c. Temporary Residents who received supplementary food during the month',
                'slug': 'programme_coverage_3',
                'rows_config': (
                    (
                        _('Number of temporary residents who received supplementary food'),
                        'thr_rations_migrant_female',
                        'thr_rations_migrant_male',
                        'thr_rations_migrant_female_1',
                        'thr_rations_migrant_male_1',
                        {
                            'columns': ('thr_rations_migrant_female', 'thr_rations_migrant_female_1'),
                            'alias': 'rations_migrant_female'
                        },
                        {
                            'columns': ('thr_rations_migrant_male', 'thr_rations_migrant_male_1'),
                            'alias': 'rations_migrant_male'
                        },
                        {
                            'columns': ('rations_migrant_female', 'rations_migrant_male'),
                            'alias': 'rations_migrant'
                        },
                        'thr_rations_migrant_pregnant',
                        'thr_rations_migrant_lactating'
                    ),
                )
            }
        ]


class MPRPreschoolEducation(ICDSMixin, MPRData):

    title = '7. Pre-school Education conducted for children 3-6 years'
    slug = 'preschool'
    has_sections = True

    @property
    def rows(self):
        if self.config['location_id']:
            data = self.custom_data(selected_location=self.selected_location, domain=self.config['domain'])
            sections = []
            for section in self.row_config:
                rows = []
                for row in section['rows_config']:
                    row_data = []
                    for idx, cell in enumerate(row):
                        if isinstance(cell, dict):
                            num = 0
                            for c in cell['columns']:
                                num += data.get(c, 0)

                            if 'second_value' in cell:
                                denom = data.get(cell['second_value'], 1)
                                alias_data = cell['func'](num, float(denom or 1))
                                cell_data = "%.1f" % cell['func'](num, float(denom or 1))
                            else:
                                cell_data = num
                                alias_data = num

                            if 'alias' in cell:
                                data[cell['alias']] = alias_data
                            row_data.append(cell_data)
                        elif isinstance(cell, tuple):
                            cell_data = 0
                            for c in cell:
                                cell_data += data.get(c, 0)
                            row_data.append(cell_data)
                        else:
                            row_data.append(data.get(cell, cell if cell == '--' or idx == 0 else 0))
                    rows.append(row_data)
                sections.append(dict(
                    title=section['title'],
                    slug=section['slug'],
                    headers=section['headers'],
                    rows=rows
                ))
            return sections

    @property
    def row_config(self):
        return [
            {
                'title': 'a. Average attendance of children for 16 or more days '
                         'in the reporting month by different categories',
                'slug': 'preschool_1',
                'headers': DataTablesHeader(
                    DataTablesColumn('Category'),
                    DataTablesColumn('Girls'),
                    DataTablesColumn('Boys'),
                    DataTablesColumn('Total')
                ),
                'rows_config': (
                    (
                        _('ST'),
                        'pse_21_days_female_st',
                        'pse_21_days_male_st',
                        {
                            'columns': ('pse_21_days_female_st', 'pse_21_days_male_st'),
                            'alias': '21_days_st'
                        }
                    ),
                    (
                        _('SC'),
                        'pse_21_days_female_sc',
                        'pse_21_days_male_sc',
                        {
                            'columns': ('pse_21_days_female_sc', 'pse_21_days_male_sc'),
                            'alias': '21_days_sc'
                        }
                    ),
                    (
                        _('Other'),
                        'pse_21_days_female_other',
                        'pse_21_days_male_other',
                        {
                            'columns': ('pse_21_days_female_other', 'pse_21_days_male_other'),
                            'alias': '21_days_other'
                        }
                    ),
                    (
                        _('All Categories (Total)'),
                        ('pse_21_days_female_st', 'pse_21_days_female_sc', 'pse_21_days_female_other'),
                        ('pse_21_days_male_st', 'pse_21_days_male_sc', 'pse_21_days_male_other'),
                        ('21_days_st', '21_days_sc', '21_days_other')
                    ),
                    (
                        _('Disabled'),
                        'pse_21_days_female_disabled',
                        'pse_21_days_male_disabled',
                        ('pse_21_days_female_disabled', 'pse_21_days_male_disabled')
                    ),
                    (
                        _('Minority'),
                        'pse_21_days_female_minority',
                        'pse_21_days_male_minority',
                        ('pse_21_days_female_minority', 'pse_21_days_male_minority')
                    )
                )

            },
            {
                'title': 'b. Total Daily Attendance of Children by age category',
                'slug': 'preschool_2',
                'headers': DataTablesHeader(
                    DataTablesColumn('Age Category'),
                    DataTablesColumn('Girls'),
                    DataTablesColumn('Boys'),
                    DataTablesColumn('Total')
                ),
                'rows_config': (
                    (
                        _('3-4 years'),
                        'pse_daily_attendance_female',
                        'pse_daily_attendance_male',
                        {
                            'columns': ('pse_daily_attendance_female', 'pse_daily_attendance_male'),
                            'alias': 'attendance_1'
                        }
                    ),
                    (
                        _('4-5 years'),
                        'pse_daily_attendance_female_1',
                        'pse_daily_attendance_male_1',
                        {
                            'columns': ('pse_daily_attendance_female_1', 'pse_daily_attendance_male_1'),
                            'alias': 'attendance_2'
                        }
                    ),
                    (
                        _('5-6 years'),
                        'pse_daily_attendance_female_2',
                        'pse_daily_attendance_male_2',
                        {
                            'columns': ('pse_daily_attendance_female_2', 'pse_daily_attendance_male_2'),
                            'alias': 'attendance_3'
                        }
                    ),
                    (
                        _('All Children'),
                        (
                            'pse_daily_attendance_female',
                            'pse_daily_attendance_female_1',
                            'pse_daily_attendance_female_2'
                        ),
                        (
                            'pse_daily_attendance_male',
                            'pse_daily_attendance_male_1',
                            'pse_daily_attendance_male_2'
                        ),
                        (
                            'attendance_1',
                            'attendance_2',
                            'attendance_3'
                        )
                    )
                )
            },
            {
                'title': 'c. PSE Attendance Efficiency',
                'slug': 'preschool_3',
                'headers': DataTablesHeader(
                    DataTablesColumn(''),
                    DataTablesColumn('Girls'),
                    DataTablesColumn('Boys'),
                    DataTablesColumn('Total')
                ),
                'rows_config': (
                    (
                        _('I. Annual Population Totals (3-6 years)'),
                        'child_count_female',
                        'child_count_male',
                        {
                            'columns': ('child_count_female', 'child_count_male'),
                            'alias': 'child_count'
                        }
                    ),
                    (
                        _('II. Usual Absentees during the month'),
                        'pse_absent_female',
                        'pse_absent_male',
                        {
                            'columns': ('pse_absent_female', 'pse_absent_male'),
                            'alias': 'absent'
                        }
                    ),
                    (
                        _('III. Total present for at least one day in month'),
                        'pse_partial_female',
                        'pse_partial_male',
                        {
                            'columns': ('pse_partial_female', 'pse_partial_male'),
                            'alias': 'partial'
                        }
                    ),
                    (
                        _('IV. Expected Total Daily Attendance'),
                        {
                            'columns': ('pse_partial_female',),
                            'func': mul,
                            'second_value': 'open_pse_count',
                            'alias': 'expected_attendance_female'
                        },
                        {
                            'columns': ('pse_partial_male',),
                            'func': mul,
                            'second_value': 'open_pse_count',
                            'alias': 'expected_attendance_male'
                        },
                        {
                            'columns': ('partial',),
                            'func': mul,
                            'second_value': 'open_pse_count',
                            'alias': 'expected_attendance'
                        }
                    ),
                    (
                        _('V. Actual Total Daily Attendance'),
                        {
                            'columns': (
                                'pse_daily_attendance_female',
                                'pse_daily_attendance_female_1',
                                'pse_daily_attendance_female_2'
                            ),
                            'alias': 'attendance_female'
                        },
                        {
                            'columns': (
                                'pse_daily_attendance_male',
                                'pse_daily_attendance_male_1',
                                'pse_daily_attendance_male_2'
                            ),
                            'alias': 'attendance_male'
                        },
                        {
                            'columns': (
                                'attendance_female',
                                'attendance_male',
                            ),
                            'alias': 'attendance'
                        }
                    ),
                    (
                        _('VI. PSE Attendance Efficiency'),
                        {
                            'columns': ('attendance_female',),
                            'func': div,
                            'second_value': 'expected_attendance_female',
                            'format': 'percent',
                        },
                        {
                            'columns': 'attendance_male',
                            'func': div,
                            'second_value': 'expected_attendance_male',
                            'format': 'percent',
                        },
                        {
                            'columns': 'attendance',
                            'func': div,
                            'second_value': 'expected_attendance',
                            'format': 'percent',
                        }
                    )
                )
            },
            {
                'title': 'd. PSE Activities',
                'slug': 'preschool_4',
                'headers': [],
                'rows_config': (
                    (
                        _('I. Average no. of days on which at least four PSE activities were conducted at AWCs'),
                        'open_four_acts_count'
                    ),
                    (
                        _('II. Average no. of days on which any PSE activity was conducted at AWCs'),
                        'open_one_acts_count'
                    )
                )
            }
        ]


class MPRGrowthMonitoring(ICDSMixin, MPRData):

    title = '8. Growth Monitoring and Classification of Nutritional Status of Children ' \
            '(as per growth chart based on the WHO Child Growth Standards)'
    slug = 'growth_monitoring'

    @property
    def rows(self):
        if self.config['location_id']:
            data = self.custom_data(selected_location=self.selected_location, domain=self.config['domain'])
            rows = []
            for row in self.row_config:
                row_data = []
                for idx, cell in enumerate(row):
                    if isinstance(cell, dict):
                        num = 0
                        if 'second_value' in cell:
                            for c in cell['columns']:
                                num += data.get(c, 0)
                            denom = data.get(cell['second_value'], 1)
                            alias_data = cell['func'](num, float(denom or 1))
                            cell_data = "%.1f" % cell['func'](num, float(denom or 1))
                        else:
                            for c in cell['columns']:
                                if 'func' in cell:
                                    if num == 0:
                                        num = data.get(c)
                                    else:
                                        num = cell['func'](num, data.get(c, 0))
                                else:
                                    num += data.get(c, 0)
                            cell_data = num
                            alias_data = num

                        if 'alias' in cell:
                            data[cell['alias']] = alias_data
                        row_data.append(cell_data)
                    elif isinstance(cell, tuple):
                        cell_data = 0
                        for c in cell:
                            cell_data += data.get(c, 0)
                        row_data.append(cell_data)
                    else:
                        row_data.append(data.get(cell, cell if cell == '--' or idx in [0, 1] else 0))
                rows.append(row_data)

            return rows

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(''),
            DataTablesColumn(''),
            DataTablesColumnGroup(
                '0 m - 1 yr',
                DataTablesColumn('Girls'),
                DataTablesColumn('Boys')
            ),
            DataTablesColumnGroup(
                '1 yr - 3 yrs',
                DataTablesColumn('Girls'),
                DataTablesColumn('Boys')
            ),
            DataTablesColumnGroup(
                '3 yrs - 5 yrs',
                DataTablesColumn('Girls'),
                DataTablesColumn('Boys')
            ),
            DataTablesColumnGroup(
                'All Children',
                DataTablesColumn('Girls'),
                DataTablesColumn('Boys'),
                DataTablesColumn('Total')
            )
        )

    @property
    def row_config(self):
        return (
            (
                'I. Total number of children weighed',
                '',
                'F_resident_weighed_count',
                'M_resident_weighed_count',
                'F_resident_weighed_count_1',
                'M_resident_weighed_count_1',
                'F_resident_weighed_count_2',
                'M_resident_weighed_count_2',
                {
                    'columns': (
                        'F_resident_weighed_count',
                        'F_resident_weighed_count_1',
                        'F_resident_weighed_count_2'
                    ),
                    'alias': 'resident_female_weight'
                },
                {
                    'columns': (
                        'M_resident_weighed_count',
                        'M_resident_weighed_count_1',
                        'M_resident_weighed_count_2'
                    ),
                    'alias': 'resident_male_weight'
                },
                {
                    'columns': ('resident_female_weight', 'resident_male_weight'),
                    'alias': 'all_resident_weight'
                },
            ),
            (
                'II. Annual Population Totals',
                '',
                'child_count_female',
                'child_count_male',
                'child_count_female_1',
                'child_count_male_1',
                'child_count_female_2',
                'child_count_male_2',
                {
                    'columns': ('child_count_female', 'child_count_female_1', 'child_count_female_2'),
                    'alias': 'child_female'
                },
                {
                    'columns': ('child_count_male', 'child_count_male_1', 'child_count_male_2'),
                    'alias': 'child_male'
                },
                {
                    'columns': ('child_female', 'child_male'),
                    'alias': 'all_child'
                },
            ),
            (
                'III. Weighing Efficiency (%)',
                '',
                {
                    'columns': ('F_resident_weighed_count',),
                    'func': div,
                    'second_value': 'child_count_female'
                },
                {
                    'columns': ('M_resident_weighed_count',),
                    'func': div,
                    'second_value': 'child_count_male'
                },
                {
                    'columns': ('F_resident_weighed_count_1',),
                    'func': div,
                    'second_value': 'child_count_female_1'
                },
                {
                    'columns': ('M_resident_weighed_count_1',),
                    'func': div,
                    'second_value': 'child_count_male_1'
                },
                {
                    'columns': ('F_resident_weighed_count_2',),
                    'func': div,
                    'second_value': 'child_count_female_2'
                },
                {
                    'columns': ('M_resident_weighed_count_2',),
                    'func': div,
                    'second_value': 'child_count_male_2'
                },
                {
                    'columns': ('resident_female_weight',),
                    'func': div,
                    'second_value': 'child_female'
                },
                {
                    'columns': ('resident_male_weight',),
                    'func': div,
                    'second_value': 'child_male'
                },
                {
                    'columns': ('all_resident_weight',),
                    'func': div,
                    'second_value': 'all_child'
                }
            ),
            (
                'IV. Out of the children weighed, no of children found:',
            ),
            (
                'a. Normal (Green)',
                'Num',
                {
                    'columns': (
                        'F_resident_weighed_count',
                        'F_mod_resident_weighed_count',
                        'F_sev_resident_weighed_count'
                    ),
                    'func': sub,
                    'alias': 'F_sub_weight'
                },
                {
                    'columns': (
                        'M_resident_weighed_count',
                        'M_mod_resident_weighed_count',
                        'M_sev_resident_weighed_count'
                    ),
                    'func': sub,
                    'alias': 'M_sub_weight'
                },
                {
                    'columns': (
                        'F_resident_weighed_count_1',
                        'F_mod_resident_weighed_count_1',
                        'F_sev_resident_weighed_count_1'
                    ),
                    'func': sub,
                    'alias': 'F_sub_weight_1'
                },
                {
                    'columns': (
                        'M_resident_weighed_count_1',
                        'M_mod_resident_weighed_count_1',
                        'M_sev_resident_weighed_count_1'
                    ),
                    'func': sub,
                    'alias': 'M_sub_weight_1'
                },
                {
                    'columns': (
                        'F_resident_weighed_count_2',
                        'F_mod_resident_weighed_count_2',
                        'F_sev_resident_weighed_count_2'
                    ),
                    'func': sub,
                    'alias': 'F_sub_weight_2'
                },
                {
                    'columns': (
                        'M_resident_weighed_count_2',
                        'M_mod_resident_weighed_count_2',
                        'M_sev_resident_weighed_count_2'
                    ),
                    'func': sub,
                    'alias': 'M_sub_weight_2'
                },
                {
                    'columns': ('F_sub_weight', 'F_sub_weight_1', 'F_sub_weight_2'),
                    'alias': 'all_F_sub_weight'
                },
                {
                    'columns': ('M_sub_weight', 'M_sub_weight_1', 'M_sub_weight_2'),
                    'alias': 'all_M_sub_weight'
                },
                {
                    'columns': ('all_F_sub_weight', 'all_M_sub_weight'),
                    'alias': 'all_sub_weight'
                }
            ),
            (
                '',
                '%',
                {
                    'columns': ('F_sub_weight',),
                    'func': div,
                    'second_value': 'F_resident_weighed_count',
                },
                {
                    'columns': ('M_sub_weight',),
                    'func': div,
                    'second_value': 'M_resident_weighed_count',
                },
                {
                    'columns': ('F_sub_weight_1',),
                    'func': div,
                    'second_value': 'F_resident_weighed_count_1',
                },
                {
                    'columns': ('M_sub_weight_1',),
                    'func': div,
                    'second_value': 'M_resident_weighed_count_1',
                },
                {
                    'columns': ('F_sub_weight_2',),
                    'func': div,
                    'second_value': 'F_resident_weighed_count_2',
                },
                {
                    'columns': ('M_sub_weight_2',),
                    'func': div,
                    'second_value': 'M_resident_weighed_count_2',
                },
                {
                    'columns': ('all_F_sub_weight',),
                    'func': div,
                    'second_value': 'resident_female_weight'
                },
                {
                    'columns': ('all_M_sub_weight',),
                    'func': div,
                    'second_value': 'resident_male_weight'
                },
                {
                    'columns': ('all_sub_weight',),
                    'func': div,
                    'second_value': 'all_resident_weight'
                },
            ),
            (
                'b. Moderately underweight (Yellow)',
                'Num',
                'F_mod_resident_weighed_count',
                'M_mod_resident_weighed_count',
                'F_mod_resident_weighed_count_1',
                'M_mod_resident_weighed_count_1',
                'F_mod_resident_weighed_count_2',
                'M_mod_resident_weighed_count_2',
                {
                    'columns': (
                        'F_mod_resident_weighed_count',
                        'F_mod_resident_weighed_count_1',
                        'F_mod_resident_weighed_count_2'),
                    'alias': 'F_sum_mod_resident_weighted'
                },
                {
                    'columns': (
                        'M_mod_resident_weighed_count',
                        'M_mod_resident_weighed_count_1',
                        'M_mod_resident_weighed_count_2'),
                    'alias': 'M_sum_mod_resident_weighted'
                },
                {
                    'columns': ('F_sum_mod_resident_weighted', 'M_sum_mod_resident_weighted'),
                    'alias': 'all_mod_resident_weighted'
                }
            ),
            (
                '',
                '%',
                {
                    'columns': ('F_mod_resident_weighed_count',),
                    'func': div,
                    'second_value': 'F_resident_weighed_count',
                },
                {
                    'columns': ('M_mod_resident_weighed_count',),
                    'func': div,
                    'second_value': 'M_resident_weighed_count',
                },
                {
                    'columns': ('F_mod_resident_weighed_count_1',),
                    'func': div,
                    'second_value': 'F_resident_weighed_count_1',
                },
                {
                    'columns': ('M_mod_resident_weighed_count_1',),
                    'func': div,
                    'second_value': 'M_resident_weighed_count_1',
                },
                {
                    'columns': ('F_mod_resident_weighed_count_2',),
                    'func': div,
                    'second_value': 'F_resident_weighed_count_2',
                },
                {
                    'columns': ('M_mod_resident_weighed_count_2',),
                    'func': div,
                    'second_value': 'M_resident_weighed_count_2',
                },
                {
                    'columns': ('F_sum_mod_resident_weighted',),
                    'func': div,
                    'second_value': 'resident_female_weight'
                },
                {
                    'columns': ('M_sum_mod_resident_weighted',),
                    'func': div,
                    'second_value': 'resident_male_weight'
                },
                {
                    'columns': ('all_mod_resident_weighted',),
                    'func': div,
                    'second_value': 'all_resident_weight'
                },
            ),
            (
                'Severely Underweight (Orange)',
                'Num',
                'F_sev_resident_weighed_count',
                'M_sev_resident_weighed_count',
                'F_sev_resident_weighed_count_1',
                'M_sev_resident_weighed_count_1',
                'F_sev_resident_weighed_count_2',
                'M_sev_resident_weighed_count_2',
                {
                    'columns': (
                        'F_sev_resident_weighed_count',
                        'F_sev_resident_weighed_count_1',
                        'F_sev_resident_weighed_count_2'),
                    'alias': 'F_sum_sev_resident_weighted'
                },
                {
                    'columns': (
                        'M_sev_resident_weighed_count',
                        'M_sev_resident_weighed_count_1',
                        'M_sev_resident_weighed_count_2'),
                    'alias': 'M_sev_mod_resident_weighted'
                },
                {
                    'columns': ('F_sev_mod_resident_weighted', 'M_sev_mod_resident_weighted'),
                    'alias': 'all_sev_resident_weighted'
                }
            ),
            (
                '',
                '%',
                {
                    'columns': ('F_sev_resident_weighed_count',),
                    'func': div,
                    'second_value': 'F_resident_weighed_count',
                },
                {
                    'columns': ('M_sev_resident_weighed_count',),
                    'func': div,
                    'second_value': 'M_resident_weighed_count',
                },
                {
                    'columns': ('F_sev_resident_weighed_count_1',),
                    'func': div,
                    'second_value': 'F_resident_weighed_count_1',
                },
                {
                    'columns': ('M_sev_resident_weighed_count_1',),
                    'func': div,
                    'second_value': 'M_resident_weighed_count_1',
                },
                {
                    'columns': ('F_sev_resident_weighed_count_2',),
                    'func': div,
                    'second_value': 'F_resident_weighed_count_2',
                },
                {
                    'columns': ('M_sev_resident_weighed_count_2',),
                    'func': div,
                    'second_value': 'M_resident_weighed_count_2',
                },
                {
                    'columns': ('F_sum_sev_resident_weighted',),
                    'func': div,
                    'second_value': 'resident_female_weight'
                },
                {
                    'columns': ('M_sum_sev_resident_weighted',),
                    'func': div,
                    'second_value': 'resident_male_weight'
                },
                {
                    'columns': ('all_sev_resident_weighted',),
                    'func': div,
                    'second_value': 'all_resident_weight'
                },
            )
        )


class MPRImmunizationCoverage(ICDSMixin, MPRData):

    title = '9. Immunization Coverage'
    slug = 'immunization_coverage'

    @property
    def rows(self):
        data = self.custom_data(selected_location=self.selected_location, domain=self.config['domain'])
        children_completing = data.get('open_child_count', 0)
        vaccination = data.get('open_child_1yr_immun_complete', 1)
        immunization = "%.1f%%" % ((children_completing / float(vaccination or 1)) * 100)
        return [
            ['(I)', 'Children Completing 12 months during the month:',  children_completing],
            ['(II)', 'Of this, number of children who have received all vaccinations:', vaccination],
            ['(III)', 'Completed timely immunization coverage (%):', immunization]
        ]

    @property
    def subtitle(self):
        if self.config['location_id']:

            return


class MPRVhnd(ICDSMixin, MPRData):

    title = '10. Village Health and Nutrition Day (VHND) activity summary'
    slug = 'vhnd'

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('Activity'),
            DataTablesColumn('No. of AWCs reported'),
            DataTablesColumn('% of AWCs reported')
        )

    @property
    def rows(self):
        if self.config['location_id']:
            data = self.custom_data(selected_location=self.selected_location, domain=self.config['domain'])
            rows = []
            for row in self.row_config:
                row_data = []
                for idx, cell in enumerate(row):
                    if isinstance(cell, dict):
                        num = data.get(cell['column'], 0)
                        row_data.append("%.1f%%" % cell['func'](num, float(self.awc_number or 1)))
                    else:
                        row_data.append(data.get(cell, cell if not cell or idx == 0 else 0))
                rows.append(row_data)
            return rows

    @property
    def row_config(self):
        return (
            (
                'a) Was VHND conducted on planned date?',
                'done_when_planned',
                {
                    'column': 'done_when_planned',
                    'func': div,
                    'second_value': 'location_number'
                }
            ),
            (
                'b) AWW present during VHND?',
                'aww_present',
                {
                    'column': 'aww_present',
                    'func': div,
                    'second_value': 'location_number'
                }
            ),
            (
                'c) ICDS Supervisor present during VHDN?',
                'icds_sup',
                {
                    'column': 'icds_sup',
                    'func': div,
                    'second_value': 'location_number'
                }
            ),
            (
                'd) ASHA present during VHND?',
                'asha_present',
                {
                    'column': 'asha_present',
                    'func': div,
                    'second_value': 'location_number'
                }
            ),
            (
                'e) ANM / MPW present during VHDN?',
                'anm_mpw',
                {
                    'column': 'anm_mpw',
                    'func': div,
                    'second_value': 'location_number'
                }
            ),
            (
                'f) Group health education conducted?',
                'health_edu_org',
                {
                    'column': 'health_edu_org',
                    'func': div,
                    'second_value': 'location_number'
                }
            ),
            (
                'g) Demonstration conducted?',
                'display_tools',
                {
                    'column': 'display_tools',
                    'func': div,
                    'second_value': 'location_number'
                }
            ),
            (
                'h) Take home rations distributed?',
                'thr_distr',
                {
                    'column': 'thr_distr',
                    'func': div,
                    'second_value': 'location_number'
                }
            ),
            (
                'i) Any children immunized?',
                'child_immu',
                {
                    'column': 'child_immu',
                    'func': div,
                    'second_value': 'location_number'
                }
            ),
            (
                'j) Vitamin A supplements administered?',
                'vit_a_given',
                {
                    'column': 'vit_a_given',
                    'func': div,
                    'second_value': 'location_number'
                }
            ),
            (
                'k) Any antenatal check-ups conducted?',
                'anc_today',
                {
                    'column': 'anc_today',
                    'func': div,
                    'second_value': 'location_number'
                }
            ),
            (
                'l) Did village leaders/VHSNC members participate?',
                'local_leader',
                {
                    'column': 'local_leader',
                    'func': div,
                    'second_value': 'location_number'
                }
            ),
            (
                'm) Was a due list prepared before the VHND for:',
                '',
                ''
            ),
            (
                'Immunization',
                'due_list_prep_immunization',
                {
                    'column': 'due_list_prep_immunization',
                    'func': div,
                    'second_value': 'location_number'
                }
            ),
            (
                'Vitamin A',
                'due_list_prep_vita_a',
                {
                    'column': 'due_list_prep_vita_a',
                    'func': div,
                    'second_value': 'location_number'
                }
            ),
            (
                'Antenatal check-ups',
                'due_list_prep_antenatal_checkup',
                {
                    'column': 'due_list_prep_antenatal_checkup',
                    'func': div,
                    'second_value': 'location_number'
                }
            )
        )


class MPRReferralServices(ICDSMixin, MPRData):

    title = '11. Referral Services'
    slug = 'referral_services'

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('Type of Problems'),
            DataTablesColumnGroup(
                'AWC referred',
                DataTablesColumn('Number'),
                DataTablesColumn('%')
            ),
            DataTablesColumn('Average no. referred to health facility'),
            DataTablesColumn('Average no. reached health facility')
        )

    @property
    def rows(self):
        if self.config['location_id']:
            data = self.custom_data(selected_location=self.selected_location, domain=self.config['domain'])
            rows = []
            for row in self.row_config:
                row_data = []
                for idx, cell in enumerate(row):
                    if isinstance(cell, dict):
                        num = 0
                        if 'second_value' in cell:
                            for c in cell['columns']:
                                num += data.get(c, 0)
                            if cell['second_value'] == 'location_number':
                                denom = self.awc_number
                            else:
                                denom = data.get(cell['second_value'], 1)
                            alias_data = cell['func'](num, float(denom or 1))
                            if 'format' in cell:
                                cell_data = "%.1f%%" % (alias_data * 100)
                            else:
                                cell_data = "%.1f" % cell['func'](num, float(denom or 1))
                        else:
                            values = []
                            for c in cell['columns']:
                                values.append(data.get(c, 0))
                            if 'func' in cell:
                                num = cell['func'](values)
                            else:
                                num = sum(values)
                            cell_data = num
                            alias_data = num

                        if 'alias' in cell:
                            data[cell['alias']] = alias_data
                        row_data.append(cell_data)
                    elif isinstance(cell, tuple):
                        cell_data = 0
                        for c in cell:
                            cell_data += data.get(c, 0)
                        row_data.append(cell_data)
                    else:
                        row_data.append(data.get(cell, cell if cell == '--' or idx == 0 else 0))
                rows.append(row_data)

            return rows

    @property
    def row_config(self):
        return (
            (
                'I. Children',
                {
                    'columns': (
                        'referred_premature',
                        'referred_sepsis',
                        'referred_diarrhoea',
                        'referred_pneumonia',
                        'referred_fever_child',
                        'referred_severely_underweight',
                        'referred_other_child'
                    ),
                    'func': max,
                    'alias': 'max_children'
                },
                {
                    'columns': ('max_children',),
                    'func': div,
                    'second_value': 'location_number',
                    'format': 'percent'
                },
                {
                    'columns': (
                        'referred_premature_all',
                        'referred_sepsis_all',
                        'referred_diarrhoea_all',
                        'referred_pneumonia_all',
                        'referred_fever_child_all',
                        'referred_severely_underweight_all',
                        'referred_other_child_all'
                    ),
                    'func': div,
                    'second_value': 'number_location'
                },
                {
                    'columns': (
                        'premature_reached_count',
                        'sepsis_reached_count',
                        'diarrhoea_reached_count',
                        'pneumonia_reached_count',
                        'fever_child_reached_count',
                        'sev_underweight_reached_count',
                        'other_child_reached_count'
                    ),
                    'func': div,
                    'second_value': 'number_location'
                },
            ),
            (
                'a. Premature',
                'referred_premature',
                {
                    'columns': ('referred_premature',),
                    'func': div,
                    'second_value': 'location_number',
                    'format': 'percent'
                },
                {
                    'columns': ('referred_premature_all',),
                    'func': div,
                    'second_value': 'location_number',
                },
                {
                    'columns': ('premature_reached_count',),
                    'func': div,
                    'second_value': 'location_number',
                }
            ),
            (
                'b. Sepsis',
                'referred_sepsis',
                {
                    'columns': ('referred_sepsis',),
                    'func': div,
                    'second_value': 'location_number',
                    'format': 'percent'
                },
                {
                    'columns': ('referred_sepsis_all',),
                    'func': div,
                    'second_value': 'location_number',
                },
                {
                    'columns': ('sepsis_reached_count',),
                    'func': div,
                    'second_value': 'location_number',
                }
            ),
            (
                'c. Diarrhea',
                'referred_diarrhoea',
                {
                    'columns': ('referred_diarrhoea',),
                    'func': div,
                    'second_value': 'location_number',
                    'format': 'percent'
                },
                {
                    'columns': ('referred_diarrhoea_all',),
                    'func': div,
                    'second_value': 'location_number',
                },
                {
                    'columns': ('diarrhoea_reached_count',),
                    'func': div,
                    'second_value': 'location_number',
                }
            ),
            (
                'd. Pneumonia',
                'referred_pneumonia',
                {
                    'columns': ('referred_pneumonia',),
                    'func': div,
                    'second_value': 'location_number',
                    'format': 'percent'
                },
                {
                    'columns': ('referred_pneumonia_all',),
                    'func': div,
                    'second_value': 'location_number',
                },
                {
                    'columns': ('pneumonia_reached_count',),
                    'func': div,
                    'second_value': 'location_number',
                }
            ),
            (
                'e. Fever',
                'referred_fever_child',
                {
                    'columns': ('referred_fever_child',),
                    'func': div,
                    'second_value': 'location_number',
                    'format': 'percent'
                },
                {
                    'columns': ('referred_fever_child_all',),
                    'func': div,
                    'second_value': 'location_number',
                },
                {
                    'columns': ('fever_child_reached_count',),
                    'func': div,
                    'second_value': 'location_number',
                }
            ),
            (
                'f. Severely underweight',
                'referred_severely_underweight',
                {
                    'columns': ('referred_severely_underweight',),
                    'func': div,
                    'second_value': 'location_number',
                    'format': 'percent'
                },
                {
                    'columns': ('referred_severely_underweight_all',),
                    'func': div,
                    'second_value': 'location_number',
                },
                {
                    'columns': ('sev_underweight_reached_count',),
                    'func': div,
                    'second_value': 'location_number',
                }
            ),
            (
                'g. Other',
                'referred_other_child',
                {
                    'columns': ('referred_other_child',),
                    'func': div,
                    'second_value': 'location_number',
                    'format': 'percent'
                },
                {
                    'columns': ('referred_other_child_all',),
                    'func': div,
                    'second_value': 'location_number',
                },
                {
                    'columns': ('other_child_reached_count',),
                    'func': div,
                    'second_value': 'location_number',
                }
            ),
            (
                'II. Pregnant and Lactating Women',
                {
                    'columns': (
                        'referred_bleeding',
                        'referred_convulsions',
                        'referred_prolonged_labor',
                        'referred_abortion_complications',
                        'referred_fever_discharge',
                        'referred_other',
                    ),
                    'func': max,
                    'alias': 'max_pregnant'
                },
                {
                    'columns': ('max_pregnant',),
                    'func': div,
                    'second_value': 'location_number',
                    'format': 'percent'
                },
                {
                    'columns': (
                        'referred_bleeding_all',
                        'referred_convulsions_all',
                        'referred_prolonged_labor_all',
                        'referred_abortion_complications_all',
                        'referred_fever_discharge_all',
                        'referred_other_all'
                    ),
                    'func': div,
                    'second_value': 'number_location'
                },
                {
                    'columns': (
                        'bleeding_reached_count',
                        'convulsions_reached_count',
                        'prolonged_labor_reached_count',
                        'abort_comp_reached_count',
                        'fever_discharge_reached_count',
                        'other_reached_count'
                    ),
                    'func': div,
                    'second_value': 'number_location'
                },
            ),
            (
                'a. Bleeding',
                'referred_bleeding',
                {
                    'columns': ('referred_bleeding',),
                    'func': div,
                    'second_value': 'location_number',
                    'format': 'percent'
                },
                {
                    'columns': ('referred_bleeding_all',),
                    'func': div,
                    'second_value': 'location_number',
                },
                {
                    'columns': ('bleeding_reached_count',),
                    'func': div,
                    'second_value': 'location_number',
                }
            ),
            (
                'b. Convulsion',
                'referred_convulsions',
                {
                    'columns': ('referred_convulsions',),
                    'func': div,
                    'second_value': 'location_number',
                    'format': 'percent'
                },
                {
                    'columns': ('referred_convulsions_all',),
                    'func': div,
                    'second_value': 'location_number',
                },
                {
                    'columns': ('convulsions_reached_count',),
                    'func': div,
                    'second_value': 'location_number',
                }
            ),
            (
                'c. Prolonged labour',
                'referred_prolonged_labor',
                {
                    'columns': ('referred_prolonged_labor',),
                    'func': div,
                    'second_value': 'location_number',
                    'format': 'percent'
                },
                {
                    'columns': ('referred_prolonged_labor_all',),
                    'func': div,
                    'second_value': 'location_number',
                },
                {
                    'columns': ('prolonged_labor_reached_count',),
                    'func': div,
                    'second_value': 'location_number',
                }
            ),
            (
                'd. Abortion complications',
                'referred_abortion_complications',
                {
                    'columns': ('referred_abortion_complications',),
                    'func': div,
                    'second_value': 'location_number',
                    'format': 'percent'
                },
                {
                    'columns': ('referred_abortion_complications_all',),
                    'func': div,
                    'second_value': 'location_number',
                },
                {
                    'columns': ('abort_comp_reached_count',),
                    'func': div,
                    'second_value': 'location_number',
                }
            ),
            (
                'e. Fever/offensive discharge after delivery',
                'referred_fever_discharge',
                {
                    'columns': ('referred_fever_discharge',),
                    'func': div,
                    'second_value': 'location_number',
                    'format': 'percent'
                },
                {
                    'columns': ('referred_fever_discharge_all',),
                    'func': div,
                    'second_value': 'location_number',
                },
                {
                    'columns': ('fever_discharge_reached_count',),
                    'func': div,
                    'second_value': 'location_number',
                }
            ),
            (
                'f. Other',
                'referred_other',
                {
                    'columns': ('referred_other',),
                    'func': div,
                    'second_value': 'location_number',
                    'format': 'percent'
                },
                {
                    'columns': ('referred_other_all',),
                    'func': div,
                    'second_value': 'location_number',
                },
                {
                    'columns': ('other_reached_count',),
                    'func': div,
                    'second_value': 'location_number',
                }
            )
        )


class MPRMonitoring(ICDSMixin, MPRData):

    title = '12. Monitoring and Supervision During the Month'
    subtitle = '(I) Visits to AWCs',
    slug = 'monitoring'

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('Visited By'),
            DataTablesColumn('No. of AWCs Visited'),
            DataTablesColumn('% of AWCs Visited')
        )

    @property
    def rows(self):
        if self.config['location_id']:
            data = self.custom_data(selected_location=self.selected_location, domain=self.config['domain'])
            rows = []
            for row in self.row_config:
                row_data = []
                for idx, cell in enumerate(row):
                    if isinstance(cell, dict):
                        num = 0
                        for c in cell['columns']:
                            num += data.get(c, 0)
                        row_data.append("%.1f%%" % cell['func'](num, float(self.awc_number or 1)))
                    else:
                        row_data.append(data.get(cell, cell if not cell or idx == 0 else 0))
                rows.append(row_data)
            return rows

    @property
    def row_config(self):
        return (
            (
                '(From AWW MPR)',
                '',
                ''
            ),
            (
                'a. ICDS Supervisor',
                'visitor_icds_sup',
                {
                    'columns': ('visitor_icds_sup',),
                    'func': div,
                    'second_value': 'location_number',
                }
            ),
            (
                'b. ANM',
                'visitor_anm',
                {
                    'columns': ('visitor_anm',),
                    'func': div,
                    'second_value': 'location_number',
                }
            ),
            (
                'c. Health Supervisor',
                'visitor_health_sup',
                {
                    'columns': ('visitor_health_sup',),
                    'func': div,
                    'second_value': 'location_number',
                }
            ),
            (
                'd. CDPO/ACDPO',
                'visitor_cdpo',
                {
                    'columns': ('visitor_cdpo',),
                    'func': div,
                    'second_value': 'location_number',
                }
            ),
            (
                'e. Medical Officer',
                'visitor_med_officer',
                {
                    'columns': ('visitor_med_officer',),
                    'func': div,
                    'second_value': 'location_number',
                }
            ),
            (
                'f. ICDS Dist Programme Officer (DPO)',
                'visitor_dpo',
                {
                    'columns': ('visitor_dpo',),
                    'func': div,
                    'second_value': 'location_number',
                }
            ),
            (
                'g. State level officials',
                'visitor_officer_state',
                {
                    'columns': ('visitor_officer_state',),
                    'func': div,
                    'second_value': 'location_number',
                }
            ),
            (
                'h. Officials from Central Government',
                'visitor_officer_central',
                {
                    'columns': ('visitor_officer_central',),
                    'func': div,
                    'second_value': 'location_number',
                }
            )
        )
