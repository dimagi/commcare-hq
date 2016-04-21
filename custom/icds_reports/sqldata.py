import json
import os
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DataTablesColumnGroup
from corehq.apps.reports_core.filters import Choice
from corehq.apps.userreports.models import ReportConfiguration
from corehq.apps.userreports.reports.factory import ReportFactory
from django.utils.translation import ugettext as _
from corehq.util.couch import get_document_or_not_found


class ICDSData(object):

    def __init__(self, domain, filters, report_id):
        report_config = ReportFactory.from_spec(
            get_document_or_not_found(
                ReportConfiguration,
                domain,
                report_id
            )
        )
        report_config.set_filter_values(filters)
        self.report_config = report_config

    def data(self):
        return self.report_config.get_data()


class ICDSMixin(object):

    @property
    def sources(self):
        with open(os.path.join(os.path.dirname(__file__), 'resources/block_mpr.json')) as f:
            return json.loads(f.read())[self.slug]

    def custom_data(self, filters, domain):
        data = {}
        for config in self.sources['data_source']:
            if 'date_filter_field' in config:
                filters.update({config['date_filter_field']: self.config['date_span']})
            report_data = ICDSData(domain, filters, config['id']).data()
            for column in config['columns']:
                column_agg_func = column['agg_fun']
                column_name = column['column_name']
                column_data = 0
                if column_agg_func == 'sum':
                    column_data = sum([x[column_name] for x in report_data])
                elif column_agg_func == 'count':
                    column_data = len(report_data)

                data.update({
                    column_name: data.get(column_name, 0) + column_data
                })
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
            key = selected_location.location_type.name.lower() + '_id'

            data = self.custom_data(
                domain=self.config['domain'],
                filters={
                    key: [Choice(value=selected_location.location_id, display=selected_location.name)],
                }
            )
            return [
                [
                    'No. of AWCs',
                    len(awc_number),
                    0,
                    data['owner_id']
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
            data = self.custom_data(
                domain=self.config['domain'],
                filters={}
            )
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
            selected_location = SQLLocation.objects.get(
                location_id=self.config['location_id']
            )
            key = selected_location.location_type.name.lower() + '_id'

            data = self.custom_data(
                domain=self.config['domain'],
                filters={
                    key: [Choice(value=selected_location.location_id, display=selected_location.name)],
                }
            )
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
