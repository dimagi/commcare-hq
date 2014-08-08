from sqlagg.columns import SimpleColumn, CountColumn
from sqlagg.filters import *
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn, TableDataFormat, DataFormatter
from custom.care_pathways.utils import get_domain_configuration

KEYS = [u'lvl_1', u'lvl_2', u'lvl_3', u'lvl_4', u'lvl_5']

class GeographySqlData(SqlData):
    table_name = "fluff_GeographyFluff"

    def __init__(self, domain):
        self.geography_config = get_domain_configuration(domain)['geography_hierarchy']
        super(GeographySqlData, self).__init__()

    @property
    def filters(self):
        return []

    @property
    def group_by(self):
        return [k for k in self.geography_config.keys()]

    @property
    def columns(self):
        levels = [k for k in self.geography_config.keys()]
        columns = []
        for k in levels:
            columns.append(DatabaseColumn(k, SimpleColumn(k)))
        return columns

class AdoptionBarChartReportSqlData(SqlData):
    table_name = 'fluff_FarmerRecordFluff'

    def __init__(self, domain, config):
        self.domain = domain
        self.geography_config = get_domain_configuration(domain)['geography_hierarchy']
        self.config = config
        super(AdoptionBarChartReportSqlData, self).__init__(config=config)

    def percent_fn(self, x, y):
        return "%(p)s%%" % \
            {
                "p": (100 * int(y or 0) / (x or 1))
            }

    @property
    def columns(self):
        return [
            DatabaseColumn('', SimpleColumn('value_chain')),
            DatabaseColumn('All', CountColumn('prop_value', alias='all')),
            DatabaseColumn('None', CountColumn('prop_value', alias='none')),
            DatabaseColumn('Some', CountColumn('prop_value', alias='some'))
        ]

    @property
    def filters(self):
        filters = [EQ("ppt_year", "year")]
        for k, v in self.geography_config.iteritems():
            if v['prop'] in self.config and self.config[v['prop']]:
                filters.append(IN(k, v['prop']))
        if 'value_chain' in self.config and self.config['value_chain']:
            filters.append(EQ("value_chain", "value_chain"))
        if 'domains' in self.config and self.config['domains']:
            filters.append(IN("domains", "domains"))
        if 'practices' in self.config and self.config['practices']:
            filters.append(IN("practices", "practices"))
        if 'gender' in self.config and self.config['gender']:
            filters.append(EQ["gender", "gender"])
        if 'group_leadership' in self.config and self.config['group_leadership']:
            filters.append(EQ('group_leadership', 'group_leadership'))
        if 'cbt_name' in self.config and self.config['cbt_name']:
            filters.append(EQ('owner_id', 'cbt_name'))
        return filters

    @property
    def group_by(self):
        group_by = ['domain', 'value_chain']

        return group_by

    @property
    def rows(self):
        formatter = DataFormatter(TableDataFormat(self.columns, no_value=self.no_value))
        return list(formatter.format(self.data, keys=self.keys, group_by=self.group_by))