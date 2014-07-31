from sqlagg.columns import SimpleColumn
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn
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