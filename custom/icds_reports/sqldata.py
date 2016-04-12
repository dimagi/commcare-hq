import json
import os
from sqlagg.columns import SimpleColumn, SumColumn, CountColumn
from sqlagg.filters import EQ, BETWEEN

from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DataTablesColumnGroup
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn
from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.apps.userreports.sql import get_table_name
from corehq.sql_db.connections import UCR_ENGINE_ID
from django.utils.translation import ugettext as _


class ICDSData(SqlData):

    def __init__(self, source=None, config=None):
        self.source = source
        super(ICDSData, self).__init__(config=config)
        data_source = DataSourceConfiguration.get(source['id'])
        self.table_name = get_table_name(self.config['domain'], data_source.table_id)

    @property
    def engine_id(self):
        return UCR_ENGINE_ID

    @property
    def filters(self):
        filters = []
        if 'location_id' in self.config and self.config['location_id']:
            type = SQLLocation.objects.get(
                location_id=self.config['location_id']
            ).location_type.name.lower()
            filters.append(EQ("%s_id" % type, 'location_id'))
        if ('start_date' in self.config and self.config['start_date'])\
                and ('end_date' in self.config and self.config['end_date']):
            filters.append(BETWEEN(self.source['date_filter_field'], 'start_date', 'end_date'))
        return filters

    @property
    def group_by(self):
        # if group_by equals location then groupo by chosen location type
        if self.source['group_by'] == "location":
            type = SQLLocation.objects.get(
                location_id=self.config['location_id']
            ).location_type.name.lower()
            return ["%s_id" % type]
        return [self.source['group_by']]

    @property
    def columns(self):
        columns = []
        for col in self.source['columns']:
            if col['agg_fun'] == 'count':
                column = CountColumn
            elif col['agg_fun'] == 'sum':
                column = SumColumn
                type = SQLLocation.objects.get(
                    location_id=self.config['location_id']
                ).location_type.name.lower()
                columns.append(DatabaseColumn('test', SimpleColumn("%s_id" % type)))

            columns.append(DatabaseColumn(col['column_name'], column(col['column_name'])))
        return columns


class ICDSMixin(object):

    @property
    def sources(self):
        with open(os.path.join(os.path.dirname(__file__), 'resources/block_mpr.json')) as f:
            return json.loads(f.read())[self.slug]

    def custom_data(self, count=False):
        data = {}
        for source in self.sources['data_source']:
            if not count:
                data.update(ICDSData(source=source, config=self.config).data.get(self.config['location_id'], {}))
            else:
                data = len(ICDSData(source=source, config=self.config).data)
        return data


class Identification(object):

    title = 'Identification'
    slug = 'identification'

    def __init__(self, config):
        self.config = config

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('', sortable=False),
            DataTablesColumn('Name', sortable=False),
            DataTablesColumn('Code', sortable=False)
        )

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


class Operationalization(ICDSMixin):

    title = 'Status of operationalization of AWCs'
    slug = 'operationalization'

    def __init__(self, config):
        self.config = config

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('', sortable=False),
            DataTablesColumn('Sanctioned', sortable=False),
            DataTablesColumn('Functioning', sortable=False),
            DataTablesColumn('Reporting', sortable=False)
        )

    @property
    def rows(self):
        if self.config['location_id']:
            selected_location = SQLLocation.objects.get(
                location_id=self.config['location_id']
            )
            awcs = selected_location.get_descendants(include_self=True).filter(
                location_type__name='awc'
            )
            awc_number = [
                loc for loc in awcs
                if 'test' not in loc.metadata and loc.metadata.get('test', '').lower() != 'yes'
            ]

            return [
                [
                    'No. of AWCs',
                    len(awc_number),
                    0,
                    self.custom_data(count=True)
                ],
                [
                    'No. of Mini AWCs',
                    0,
                    0,
                    0
                ]
            ]


class Sectors(object):

    title = 'No of Sectors'
    slug = 'sectors'

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


class Population(ICDSMixin):

    title = 'Total Population of Project'
    slug = 'population'

    def __init__(self, config):
        self.config = dict(
            domain=config['domain'],
            location_id=config['location_id']
        )

    @property
    def headers(self):
        return []

    @property
    def rows(self):
        if self.config['location_id']:
            data = self.custom_data()
            return [
                [
                    "Total Population of the project (as of last April):",
                    data['open_count']
                ]
            ]


class BirthsAndDeaths(ICDSMixin):

    title = 'Details of Births and Deaths during the month'
    slug = 'births_and_deaths'

    def __init__(self, config):
        self.config = config

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_('Si No')),
            DataTablesColumn(_('Categories')),
            DataTablesColumnGroup(
                _('Among Permanent Residents'),
                DataTablesColumn(_('Girls/Women'), sortable=False),
                DataTablesColumn(_('Boys'), sortable=False),
            ),
            DataTablesColumnGroup(
                _('Among Permanent Residents'),
                DataTablesColumn(_('Girls/Women'), sortable=False),
                DataTablesColumn(_('Boys'), sortable=False),
            )
        )

    @property
    def rows(self):
        if self.config['location_id']:
            custom_data = self.custom_data()
            rows = []
            for row in self.row_config:
                row_data = []
                for idx, cell in enumerate(row):
                    if isinstance(cell, tuple):
                        x = custom_data.get(cell[0], 0)
                        y = custom_data.get(cell[1], 0)
                        row_data.append(x + y)
                    else:
                        row_data.append(custom_data.get(cell, cell if cell == '--' or idx in [0, 1] else 0))
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
