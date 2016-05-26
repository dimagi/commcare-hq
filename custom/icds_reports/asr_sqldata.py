import itertools
import string

from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DataTablesColumnGroup
from custom.icds_reports.sqldata import BaseIdentification, BasePopulation, BaseOperationalization
from custom.icds_reports.utils import ASRData, ICDSMixin


class ASRIdentification(BaseIdentification):

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
            descendant_locations = SQLLocation.objects.get(
                location_id=self.config['location_id']
            ).get_descendants(include_self=True)
            supervisor = [
                s for s in descendant_locations.filter(location_type__name='supervisor')
                if 'test' not in s.metadata and s.metadata.get('test', '').lower() != 'yes'
            ]
            rows.append([
                'Number of Sectors', len(supervisor), ''
            ])
            return rows


class ASROperationalization(BaseOperationalization, ASRData):
    pass


class ASRPopulation(BasePopulation, ASRData):

    title = 'Details of Annual Family Survey'


class Annual(ICDSMixin, ASRData):

    title = 'Annual Population Summary'
    slug = 'annual'
    has_sections = True

    @property
    def rows(self):
        if self.config['location_id']:
            sections = []
            rows = [
                ['ST'],
                ['SC'],
                ['Others'],
                ['Total'],
                ['Minority']
            ]
            one_letter = [''.join(p) for p in itertools.product(string.ascii_lowercase, repeat=1)]
            two_letters = [''.join(p) for p in itertools.product(string.ascii_lowercase, repeat=2)]
            all_letters = one_letter + two_letters

            for i in range(0, 15):
                for row in rows:
                    row.append(all_letters[0])
                    del all_letters[0]
            rows.insert(0, range(1, 17))
            sections.append(dict(
                title=self.row_config[0]['title'],
                headers=self.row_config[0]['headers'],
                slug=self.row_config[0]['slug'],
                rows=rows,
                posttitle='(this table above shows the format, the letters '
                          'a-o represent the data, which appears in the table below)'
            ))
            data = self.custom_data(selected_location=self.selected_location, domain=self.config['domain'])
            rr = []
            for row in self.row_config[1]['rows_config']:
                row_data = []
                for idx, cell in enumerate(row):
                    if 0 <= idx <= 2:
                        row_data.append(cell)
                    else:
                        num = 0
                        for c in cell:
                            num += data.get(c, 0)
                        row_data.append(num)
                rr.append(row_data)
            sections.append(dict(
                title=self.row_config[1]['title'],
                headers=self.row_config[1]['headers'],
                slug=self.row_config[1]['slug'],
                rows=rr,
                posttitle=None
            ))
            return sections

    @property
    def row_config(self):
        return [
            {
                'title': '',
                'slug': 'annual_1',
                'headers': DataTablesHeader(
                    DataTablesColumn('Category'),
                    DataTablesColumn('PW'),
                    DataTablesColumn('LM'),
                    DataTablesColumnGroup(
                        'Children 0-5 months',
                        DataTablesColumn('B'),
                        DataTablesColumn('G')
                    ),
                    DataTablesColumnGroup(
                        'Children 6-11 months',
                        DataTablesColumn('B'),
                        DataTablesColumn('G')
                    ),
                    DataTablesColumnGroup(
                        'Children 12-35 months',
                        DataTablesColumn('B'),
                        DataTablesColumn('G')
                    ),
                    DataTablesColumnGroup(
                        'Children 36-59 months',
                        DataTablesColumn('B'),
                        DataTablesColumn('G')
                    ),
                    DataTablesColumnGroup(
                        'Children 60-71 months',
                        DataTablesColumn('B'),
                        DataTablesColumn('G')
                    ),
                    DataTablesColumnGroup(
                        'All Children 0-71 months',
                        DataTablesColumn('B'),
                        DataTablesColumn('G')
                    ),
                    DataTablesColumn('AG')
                )
            },
            {
                'title': '',
                'slug': 'annual_2',
                'headers': DataTablesHeader(
                    DataTablesColumn('Diagram Reference #'),
                    DataTablesColumn('Diagram Reference label'),
                    DataTablesColumn('Report Reference #'),
                    DataTablesColumn('Value')
                ),
                'rows_config': (
                    (
                        'a',
                        'PW ST',
                        '#2',
                        ('pregnant_st_count',)
                    ),
                    (
                        'b',
                        'PW SC',
                        '#2',
                        ('pregnant_sc_count',)
                    ),
                    (
                        'c',
                        'PW Other',
                        '#2',
                        ('pregnant_other_count',)
                    ),
                    (
                        'd',
                        'PW Total',
                        '--',
                        ('pregnant_st_count', 'pregnant_sc_count', 'pregnant_other_count')
                    ),
                    (
                        'e',
                        'PW Minority',
                        '#2',
                        ("delivered_minority_count",)
                    ),
                    (
                        'f',
                        'LM ST',
                        '#3',
                        ("delivered_st_count",)
                    ),
                    (
                        'g',
                        'LM SC',
                        '#3',
                        ("delivered_sc_count",)
                    ),
                    (
                        'h',
                        'LM Others',
                        '#3',
                        ("delivered_other_count",)
                    ),
                    (
                        'i',
                        'LM Total',
                        '--',
                        ('delivered_st_count', 'delivered_sc_count', 'delivered_other_count')
                    ),
                    (
                        'j',
                        'LM Minority',
                        '#3',
                        ("delivered_minority_count",)
                    ),
                    (
                        'k',
                        '0-5 months B ST',
                        '#4',
                        ("M_st_count",)
                    ),
                    (
                        'l',
                        '0-5 months B SC',
                        '#4',
                        ("M_sc_count",)
                    ),
                    (
                        'm',
                        '0-5 months B Others',
                        '#4',
                        ("M_other_count",)
                    ),
                    (
                        'n',
                        '0-5 months B Total',
                        '--',
                        ('M_st_count', 'M_sc_count', 'M_other_count')
                    ),
                    (
                        'o',
                        '0-5 months B Minority',
                        '#4',
                        ("M_minority_count",)
                    ),
                    (
                        'p',
                        '0-5 months G ST',
                        '#4',
                        ("F_st_count",)
                    ),
                    (
                        'q',
                        '0-5 months G SC',
                        '#4',
                        ("F_sc_count",)
                    ),
                    (
                        'r',
                        '0-5 months G Others',
                        '#4',
                        ("F_other_count",)
                    ),
                    (
                        's',
                        '0-5 months G Total',
                        '--',
                        ('F_st_count', 'F_sc_count', 'F_other_count')
                    ),
                    (
                        't',
                        '0-5 months G Minority',
                        '#4',
                        ("F_minority_count",)
                    ),
                    (
                        'u',
                        '6-11 months B ST',
                        '#5',
                        ("M_st_count_1",)
                    ),
                    (
                        'v',
                        '6-11 months B SC',
                        '#5',
                        ("M_sc_count_1",)
                    ),
                    (
                        'w',
                        '6-11 months B Others',
                        '#5',
                        ("M_other_count_1",)
                    ),
                    (
                        'x',
                        '6-11 months B Total',
                        '--',
                        ('M_st_count_1', 'M_sc_count_1', 'M_other_count_1')
                    ),
                    (
                        'y',
                        '6-11 months B Minority',
                        '#5',
                        ("M_minority_count_1",)
                    ),
                    (
                        'z',
                        '6-11 months G ST',
                        '#5',
                        ("F_st_count_1",)
                    ),
                    (
                        'aa',
                        '6-11 months G SC',
                        '#5',
                        ("F_sc_count_1",)
                    ),
                    (
                        'ab',
                        '6-11 months G Others',
                        '#5',
                        ("F_other_count_1",)
                    ),
                    (
                        'ac',
                        '6-11 months G Total',
                        '--',
                        ('F_st_count_1', 'F_sc_count_1', 'F_other_count_1')
                    ),
                    (
                        'ad',
                        '6-11 months G Minority',
                        '#5',
                        ("F_minority_count_1",)
                    ),
                    (
                        'ae',
                        '12-35 months B ST',
                        '#6',
                        ("M_st_count_2",)
                    ),
                    (
                        'af',
                        '12-35 months B SC',
                        '#6',
                        ("M_sc_count_2",)
                    ),
                    (
                        'ag',
                        '12-35 months B Others',
                        '#6',
                        ("M_other_count_2",)
                    ),
                    (
                        'ah',
                        '12-35 months G Total',
                        '--',
                        ('M_st_count_2', 'M_sc_count_2', 'M_other_count_2')
                    ),
                    (
                        'ai',
                        '12-35 months B Minority',
                        '#6',
                        ("M_minority_count_2",)
                    ),
                    (
                        'aj',
                        '12-35 months G ST',
                        '#6',
                        ("F_st_count_2",)
                    ),
                    (
                        'ak',
                        '12-35 months G SC',
                        '#6',
                        ("F_sc_count_2",)
                    ),
                    (
                        'al',
                        '12-35 months G Others',
                        '#6',
                        ("F_other_count_2",)
                    ),
                    (
                        'am',
                        '12-35 months G Total',
                        '--',
                        ('F_st_count_2', 'F_sc_count_2', 'F_other_count_2')
                    ),
                    (
                        'an',
                        '12-35 months G Minority',
                        '#6',
                        ("F_minority_count_2",)
                    ),
                    (
                        'ao',
                        '36-59 months B ST',
                        '#7',
                        ("M_st_count_3",)
                    ),
                    (
                        'ap',
                        '36-59 months B SC',
                        '#7',
                        ("M_sc_count_3",)
                    ),
                    (
                        'aq',
                        '36-59 months B Others',
                        '#7',
                        ("M_other_count_3",)
                    ),
                    (
                        'ar',
                        '36-59 months G Total',
                        '--',
                        ('M_st_count_3', 'M_sc_count_3', 'M_other_count_3')
                    ),
                    (
                        'as',
                        '36-59 months B Minority',
                        '#7',
                        ("M_minority_count_3",)
                    ),
                    (
                        'at',
                        '36-59 months G ST',
                        '#7',
                        ("F_st_count_3",)
                    ),
                    (
                        'au',
                        '36-59 months G SC',
                        '#7',
                        ("F_sc_count_3",)
                    ),
                    (
                        'av',
                        '36-59 months G Others',
                        '#7',
                        ("F_other_count_3",)
                    ),
                    (
                        'aw',
                        '36-59 months G Total',
                        '--',
                        ('F_st_count_3', 'F_sc_count_3', 'F_other_count_3')
                    ),
                    (
                        'ax',
                        '36-59 months G Minority',
                        '#7',
                        ("F_minority_count_3",)
                    ),
                    (
                        'ay',
                        '60-71 months B ST',
                        '#8',
                        ("M_st_count_4",)
                    ),
                    (
                        'az',
                        '60-71 months B SC',
                        '#8',
                        ("M_sc_count_4",)
                    ),
                    (
                        'ba',
                        '60-71 months B Others',
                        '#8',
                        ("M_other_count_4",)
                    ),
                    (
                        'bb',
                        '60-71 months G Total',
                        '--',
                        ('M_st_count_4', 'M_sc_count_4', 'M_other_count_4')
                    ),
                    (
                        'bc',
                        '60-71 months B Minority',
                        '#8',
                        ("M_minority_count_4",)
                    ),
                    (
                        'bd',
                        '60-71 months G ST',
                        '#8',
                        ("F_st_count_4",)
                    ),
                    (
                        'be',
                        '60-71 months G SC',
                        '#8',
                        ("F_sc_count_4",)
                    ),
                    (
                        'bf',
                        '60-71 months G Others',
                        '#8',
                        ("F_other_count_4",)
                    ),
                    (
                        'bg',
                        '60-71 months G Total',
                        '--',
                        ('F_st_count_4', 'F_sc_count_4', 'F_other_count_4')
                    ),
                    (
                        'bh',
                        '60-71 months G Minority',
                        '#8',
                        ("F_minority_count_4",)
                    ),
                    (
                        'bi',
                        '0-71 months B ST',
                        '#9',
                        ("M_st_count_all",)
                    ),
                    (
                        'bj',
                        '0-71 months B SC',
                        '#9',
                        ("M_sc_count_all",)
                    ),
                    (
                        'bk',
                        '0-71 months B Others',
                        '#9',
                        ("M_other_count_all",)
                    ),
                    (
                        'bl',
                        '0-71 months G Total',
                        '--',
                        ('M_st_count_all', 'M_sc_count_all', 'M_other_count_all')
                    ),
                    (
                        'bm',
                        '0-71 months B Minority',
                        '#9',
                        ("M_minority_count_all",)
                    ),
                    (
                        'bn',
                        '0-71 months G ST',
                        '#9',
                        ("F_st_count_all",)
                    ),
                    (
                        'bo',
                        '0-71 months G SC',
                        '#9',
                        ("F_sc_count_all",)
                    ),
                    (
                        'bp',
                        '0-71 months G Others',
                        '#9',
                        ("F_other_count_all",)
                    ),
                    (
                        'bq',
                        '0-71 months G Total',
                        '--',
                        ('F_st_count_all', 'F_sc_count_all', 'F_other_count_all')
                    ),
                    (
                        'br',
                        '0-71 months G Minority',
                        '#9',
                        ("F_minority_count_all",)
                    ),
                    (
                        'bs',
                        'AG ST',
                        '#10',
                        ("M_st_count_ag",)
                    ),
                    (
                        'bt',
                        'AG SC',
                        '#10',
                        ("M_sc_count_ag",)
                    ),
                    (
                        'bu',
                        'AG Other',
                        '#10',
                        ("M_other_count_ag",)
                    ),
                    (
                        'bv',
                        'AG Total',
                        '--',
                        ('M_st_count_ag', 'M_sc_count_ag', 'M_other_count_ag')
                    ),
                    (
                        'bw',
                        'AG minority',
                        '#10',
                        ("M_minority_count_ag",)
                    )
                )
            }
        ]


class DisabledChildren(ICDSMixin, ASRData):

    title = 'Identification of disabled children'
    slug = 'disabled_children'

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('#'),
            DataTablesColumn('Category'),
            DataTablesColumn('SubCategory'),
            DataTablesColumn('Reports'),
            DataTablesColumn('Report Variable')
        )

    @property
    def rows(self):
        if self.config['location_id']:
            data = self.custom_data(selected_location=self.selected_location, domain=self.config['domain'])
            rows = []
            for row in self.row_config:
                row_data = []
                for idx, cell in enumerate(row):
                    if 0 <= idx <= 3:
                        row_data.append(cell)
                    else:
                        num = 0
                        for c in cell:
                            num += data.get(c, 0)
                        row_data.append(num)
                rows.append(row_data)
            return rows

    @property
    def row_config(self):
        return (
            (
                'a',
                'No. of children 0-3 yrs',
                'Movement',
                '#4 + #5 + #6',
                ('disabled_movement_count',)
            ),
            (
                'b',
                '',
                'Mental',
                '#4 + #5 + #6',
                ('disabled_mental_count',)
            ),
            (
                'c',
                '',
                'Seeing',
                '#4 + #5 + #6',
                ('disabled_seeing_count',)
            ),
            (
                'd',
                '',
                'Hearing',
                '#4 + #5 + #6',
                ('disabled_hearing_count',)
            ),
            (
                'e',
                '',
                'Speaking',
                '#4 + #5 + #6',
                ('disabled_speaking_count',)
            ),
            (
                'f',
                '',
                'Total',
                'na',
                (
                    'disabled_movement_count',
                    'disabled_mental_count',
                    'disabled_seeing_count',
                    'disabled_hearing_count',
                    'disabled_speaking_count'
                )
            ),
            (
                'g',
                'No. of children 3-6 yrs',
                'Movement',
                '#7 + #8',
                ('disabled_movement_count_1',)
            ),
            (
                'h',
                '',
                'Mental',
                '#7 + #8',
                ('disabled_mental_count_1',)
            ),
            (
                'i',
                '',
                'Seeing',
                '#7 + #8',
                ('disabled_seeing_count_1',)
            ),
            (
                'j',
                '',
                'Hearing',
                '#7 + #8',
                ('disabled_hearing_count_1',)
            ),
            (
                'k',
                '',
                'Speaking',
                '#7 + #8',
                ('disabled_speaking_count_1',)
            ),
            (
                'l',
                '',
                'Total',
                'na',
                (
                    'disabled_movement_count_1',
                    'disabled_mental_count_1',
                    'disabled_seeing_count_1',
                    'disabled_hearing_count_1',
                    'disabled_speaking_count_1'
                )
            ),
            (
                'm',
                'Total',
                'Movement',
                'na',
                ('disabled_movement_count', 'disabled_movement_count_1')
            ),
            (
                'n',
                '',
                'Mental',
                'na',
                ('disabled_mental_count', 'disabled_mental_count_1')
            ),
            (
                'i',
                '',
                'Seeing',
                'na',
                ('disabled_seeing_count', 'disabled_seeing_count_1')
            ),
            (
                'j',
                '',
                'Hearing',
                'na',
                ('disabled_hearing_count', 'disabled_hearing_count_1')
            ),
            (
                'k',
                '',
                'Speaking',
                'na',
                ('disabled_speaking_count', 'disabled_speaking_count_1')
            ),
            (
                'l',
                '',
                'Total',
                'na',
                (
                    'disabled_movement_count',
                    'disabled_mental_count',
                    'disabled_seeing_count',
                    'disabled_hearing_count',
                    'disabled_speaking_count',
                    'disabled_movement_count_1',
                    'disabled_mental_count_1',
                    'disabled_seeing_count_1',
                    'disabled_hearing_count_1',
                    'disabled_speaking_count_1'
                )
            )
        )


class Infrastructure(ICDSMixin, ASRData):

    title = 'Infrastructure Status'
    slug = 'infrastructure'
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
                        if idx < section['static_cell']:
                            row_data.append(cell)
                        else:
                            row_data.append(data.get(cell, 0))
                    rows.append(row_data)
                sections.append(dict(
                    title=section['title'],
                    headers=section['headers'],
                    slug=section['slug'],
                    rows=rows
                ))
            return sections

    @property
    def row_config(self):
        return [
            {
                'title': 'Status of AWC buildings',
                'slug': 'infrastructure_1',
                'static_cell': 1,
                'headers': DataTablesHeader(
                    DataTablesColumn(''),
                    DataTablesColumn('Own Building'),
                    DataTablesColumn('Rented Building'),
                    DataTablesColumn('Neither own nor rented')
                ),
                'rows_config': (
                    (
                        'No. of AWCs running in',
                        'where_housed_1',
                        'where_housed_2',
                        'where_housed_3',
                    ),
                )
            },
            {
                'title': 'If NOT in own building, number of AWCs housed in:',
                'slug': 'infrastructure_2',
                'headers': [],
                'static_cell': 2,
                'rows_config': (
                    (
                        '1',
                        "AWW's House",
                        'other_building_1'
                    ),
                    (
                        '2',
                        "AWH's House",
                        'other_building_2'
                    ),
                    (
                        '3',
                        "Community Building",
                        'other_building_3'
                    ),
                    (
                        '4',
                        "Primary School",
                        'other_building_4'
                    ),
                    (
                        '5',
                        "Any Religious Place",
                        'other_building_5'
                    ),
                    (
                        '6',
                        "Open Space",
                        'other_building_6'
                    )
                )
            },
            {
                'title': 'Type of AWC building',
                'slug': 'infrastructure_3',
                'static_cell': 1,
                'headers': DataTablesHeader(
                    DataTablesColumn(''),
                    DataTablesColumn('Pucca'),
                    DataTablesColumn('Semi Pucca'),
                    DataTablesColumn('Kutcha')
                ),
                'rows_config': (
                    (
                        'No. of AWCs',
                        'awc_building_1',
                        'awc_building_2',
                        'awc_building_3'
                    ),
                )
            },
            {
                'title': 'Toilet facilities at the AWC',
                'slug': 'infrastructure_4',
                'static_cell': 1,
                'headers': DataTablesHeader(
                    DataTablesColumn(''),
                    DataTablesColumn('Pit Type (Latrine)'),
                    DataTablesColumn('Only urinal'),
                    DataTablesColumn('Flush system'),
                    DataTablesColumn('Others'),
                    DataTablesColumn('No Facility')
                ),
                'rows_config': (
                    (
                        'No. of AWCs',
                        'type_toilet_1',
                        'type_toilet_2',
                        'type_toilet_3',
                        'type_toilet_4',
                        'toilet_facility'
                    ),
                )
            },
            {
                'title': 'Source of potable water at the AWC',
                'slug': 'infrastructure_5',
                'static_cell': 1,
                'headers': DataTablesHeader(
                    DataTablesColumn(''),
                    DataTablesColumn('Hand pump/Tube well'),
                    DataTablesColumn('Tap water'),
                    DataTablesColumn('Open well'),
                    DataTablesColumn('Others')
                ),
                'rows_config': (
                    (
                        'No. of AWCs',
                        'source_drinking_water_1',
                        'source_drinking_water_2',
                        'source_drinking_water_3',
                        'source_drinking_water_4'
                    ),
                )
            },
            {
                'title': 'Source of potable water at the AWC',
                'slug': 'infrastructure_5',
                'static_cell': 2,
                'headers': DataTablesHeader(
                    DataTablesColumn(''),
                    DataTablesColumn('Having Facilities'),
                    DataTablesColumn('No. of AWCs')
                ),
                'rows_config': (
                    (
                        'I',
                        'kitchen/separately covered space for cooking:',
                        'kitchen'
                    ),
                    (
                        'II',
                        'proper storage facility',
                        'space_storing_supplies'
                    ),
                    (
                        'III',
                        'adequate indoor space for PSE activities',
                        'space_pse_1'
                    ),
                    (
                        'IV',
                        'adequate outdoor space for PSE activities',
                        'space_pse_2'
                    ),
                    (
                        'V',
                        'adequate indoor and outdoor space for PSE activities',
                        'space_pse_3'
                    ),
                )
            }
        ]


class Equipment(ICDSMixin, ASRData):

    title = 'No. of AWCs where the following equipment and materials are available/usable:'
    slug = 'equipment'

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('#'),
            DataTablesColumn('Equipment & Materials'),
            DataTablesColumn('Available'),
            DataTablesColumn('Usable'),
            DataTablesColumn('Not Available'),
            DataTablesColumn('No. of AWCs requiring replacement')
        )

    @property
    def rows(self):
        if self.config['location_id']:
            data = self.custom_data(selected_location=self.selected_location, domain=self.config['domain'])
            rows = []
            for row in self.row_config:
                row_data = []
                for idx, cell in enumerate(row):
                    if idx < 2:
                        row_data.append(cell)
                    else:
                        row_data.append(sum([data.get(c, 0) for c in cell]))
                rows.append(row_data)
            return rows

    @property
    def row_config(self):
        return (
            (
                'A',
                'Medicine Kit',
                ('medicine_kits_available_1',),
                ('medicine_kits_usable_1',),
                ('medicine_kits_available_2',),
                ('medicine_kits_available_2', 'medicine_kits_usable_2')
            ),
            (
                'B',
                'Pre-School Kit',
                ('preschool_kit_available_1',),
                ('preschool_kit_usable_1',),
                ('preschool_kit_available_2',),
                ('preschool_kit_available_2', 'preschool_kit_usable_2'),
            ),
            (
                'C',
                'Baby weighing scale',
                ('baby_scale_available_1',),
                ('baby_scale_usable_1',),
                ('baby_scale_available_2',),
                ('baby_scale_available_2', 'baby_scale_usable_2'),
            ),
            (
                'D',
                'Flat weighing scale',
                ('flat_scale_available_1',),
                ('flat_scale_usable_1',),
                ('flat_scale_available_2',),
                ('flat_scale_available_2', 'flat_scale_usable_2'),
            ),
            (
                'E',
                'Adult weighing scale',
                ('adult_scale_available_1',),
                ('adult_scale_usable_1',),
                ('adult_scale_available_2',),
                ('adult_scale_available_2', 'adult_scale_usable_2')
            ),
            (
                'F',
                'Cooking utensils',
                ('cooking_utensils_available_1',),
                ('cooking_utensils_usable_1',),
                ('cooking_utensils_available_2',),
                ('cooking_utensils_available_2', 'cooking_utensils_usable_2')
            ),
            (
                'I',
                'IEC/BCC Materials',
                ('iec_bcc_available_1',),
                ('iec_bcc_usable_1',),
                ('iec_bcc_available_2',),
                ('iec_bcc_available_2', 'iec_bcc_usable_2')
            ),
            (
                'J',
                'NHED Kit',
                ('nhed_kit_available_1',),
                ('nhed_kit_usable_1',),
                ('nhed_kit_available_2',),
                ('nhed_kit_available_2', 'nhed_kit_usable_2')
            ),
            (
                'K',
                'Referral Slip',
                ('referral_slip_available_1',),
                ('referral_slip_usable_1',),
                ('referral_slip_available_2',),
                ('referral_slip_available_2', 'referral_slip_usable_2')
            ),
            (
                'L',
                'Plates',
                ('plates_available_1',),
                ('plates_usable_1',),
                ('plates_available_2',),
                ('plates_available_2', 'plates_usable_2')
            ),
            (
                'M',
                'Tumblers',
                ('tumblers_available_1',),
                ('tumblers_usable_1',),
                ('tumblers_available_2',),
                ('tumblers_available_2', 'tumblers_usable_2')
            ),
            (
                'N',
                'Measuring cups',
                ('measure_cups_available_1',),
                ('measure_cups_usable_1',),
                ('measure_cups_available_2',),
                ('measure_cups_available_2', 'measure_cups_usable_2')
            ),
            (
                'O',
                'Food storage bins',
                ('food_storage_available_1',),
                ('food_storage_usable_1',),
                ('food_storage_available_2',),
                ('food_storage_available_2', 'food_storage_usable_2')
            ),
            (
                'P',
                'Water storage container',
                ('water_storage_available_1',),
                ('water_storage_usable_1',),
                ('water_storage_available_2',),
                ('water_storage_available_2', 'water_storage_usable_2')
            ),
            (
                'Q',
                'Chair',
                ('chair_available_1',),
                ('chair_usable_1',),
                ('chair_available_2',),
                ('chair_available_2', 'chair_usable_2')
            ),
            (
                'R',
                'Table',
                ('table_available_1',),
                ('table_usable_1',),
                ('table_available_2',),
                ('table_available_2', 'table_usable_2')
            ),
            (
                'S',
                'Dari/Mats',
                ('mats_available_1',),
                ('mats_usable_1',),
                ('mats_available_2',),
                ('mats_available_2', 'mats_usable_2')
            ),
        )
