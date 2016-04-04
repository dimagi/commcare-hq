from sqlagg.base import AggregateColumn, AliasColumn
from sqlagg.columns import SimpleColumn, SumColumn
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DataTablesColumnGroup
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn
from corehq.apps.userreports.sql import get_table_name
from corehq.sql_db.connections import UCR_ENGINE_ID
from django.utils.translation import ugettext as _


class ICDSData(SqlData):

    @property
    def engine_id(self):
        return UCR_ENGINE_ID

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], 'icds')

    @property
    def filters(self):
        return []

    @property
    def group_by(self):
        return []

    @property
    def keys(self):
        return []

    @property
    def headers(self):
        return []

    @property
    def row_headers(self):
        return ()


class Identification(object):

    def __init__(self, config):
        self.config = config

    @property
    def headers(self):
        return DataTablesHeader([
            DataTablesColumn('', sortable=False),
            DataTablesColumn('Name', sortable=False),
            DataTablesColumn('Code', sortable=False)
        ])

    @property
    def rows(self):
        chosen_location = SQLLocation.objects.get(
            location_id=self.config['location_id']
        ).get_ancestors(include_self=True)
        rows = []
        for loc_type in ['State', 'District', 'Block']:
            loc = chosen_location.filter(location_type__name=loc_type)
            if len(loc) == 1:
                rows.append([loc_type, loc.name, loc.site_code])
            else:
                rows.append([loc_type, '', ''])
        return rows


class Operationalization(ICDSData):

    @property
    def columns(self):
        return [
            DatabaseColumn('No. of AWCs', SumColumn('number_awcs')),
            DatabaseColumn('No. of Mini AWCs', SumColumn('number_awcs'))
        ]

    @property
    def headers(self):
        return DataTablesHeader([
            DataTablesColumn('', sortable=False),
            DataTablesColumn('Sanctioned', sortable=False),
            DataTablesColumn('Functioning', sortable=False),
            DataTablesColumn('Reporting', sortable=False)
        ])

    @property
    def row_headers(self):
        return (
            (_('No. of AWCs'),),
            (_('No. of Mini AWCs'),)
        )


class Sectors(ICDSData):

    @property
    def columns(self):
        return [
            SimpleColumn(''),
            DatabaseColumn('', SimpleColumn('sectors'))
        ]

    @property
    def row_headers(self):
        return (
            (_('Number of Sectors'),),
        )


class Population(ICDSData):

    @property
    def columns(self):
        return [
            SimpleColumn(''),
            DatabaseColumn('', SimpleColumn('population'))
        ]

    @property
    def row_headers(self):
        return (
            (_('Total Population of the project (as of last April):'),),
        )


class BirthsAndDeaths(ICDSData):

    @property
    def group_by(self):
        return ['gender', 'type_of_resident']

    @property
    def headers(self):
        return DataTablesHeader([
            DataTablesColumn(_('Si No')),
            DataTablesColumn(_('Categories')),
            DataTablesColumnGroup(_('Among Permanent Residents'), [
                DataTablesColumn(_('Girls/Women'), sortable=False),
                DataTablesColumn(_('Boys'), sortable=False),
            ]),
            DataTablesColumnGroup(_('Among Permanent Residents'), [
                DataTablesColumn(_('Girls/Women'), sortable=False),
                DataTablesColumn(_('Boys'), sortable=False),
            ])
        ])

    @property
    def columns(self):
        sum = lambda x, y: (x or 0) + (y or 0)
        return [
            DatabaseColumn('live_birth', SumColumn('live_birth')),
            DatabaseColumn('still_birth', SumColumn('still_birth')),
            DatabaseColumn('weighed_birth', SumColumn('weighed_birth')),
            DatabaseColumn('lbw_birth', SumColumn('lbw_birth')),
            DatabaseColumn('dead_neo', SumColumn('dead_neo', alias='neo')),
            DatabaseColumn('dead_postneo', SumColumn('dead_postneo', alias='postneo')),
            AggregateColumn(sum, [AliasColumn('neo'), AliasColumn('postneo')]),
            DatabaseColumn('dead_child', SumColumn('dead_child')),
            DatabaseColumn('dead_adult', SumColumn('dead_adult')),
            DatabaseColumn('dead_pre', SumColumn('dead_pre')),
            DatabaseColumn('dead_del', SumColumn('dead_del')),
            DatabaseColumn('dead_pnc', SumColumn('dead_pnc'))
        ]

    @property
    def row_headers(self):
        return (
            (_('A'), _('No. of live births')),
            (_('B'), _('No. of babies born dead')),
            (_('C'), _('No. of babies weighed within 3 days of birth')),
            (_('D'), _('Out of the above, no. of low birth weight babies (< 2500 gm)')),
            (_('E'), _('No. of neonatal deaths (within 28 days of birth)')),
            (_('F'), _('No. of post neonatal deaths (between 29 days and 12 months of birth)')),
            (_('G'), _('Total infant deaths (E+F)')),
            (_('H'), _('Total child deaths (1- 5 years)')),
            (_('I'), _('No. of deaths of women')),
            ('', _('a. during pregnancy')),
            ('', _('b. during delivery')),
            ('', _('c. within 42 days of delivery')),
        )
