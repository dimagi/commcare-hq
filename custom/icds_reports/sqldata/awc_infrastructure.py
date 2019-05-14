from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from sqlagg.columns import SimpleColumn
from sqlagg.filters import EQ, IN

from corehq.apps.reports.sqlreport import DatabaseColumn
from corehq.apps.reports.util import get_INFilter_bindparams
from corehq.apps.userreports.util import get_table_name
from custom.icds_reports.sqldata.base import IcdsSqlData
from custom.utils.utils import clean_IN_filter_value


class AWCInfrastructureUCR(IcdsSqlData):
    def __init__(self, config):
        self.awcs = config['awc_id']
        super(AWCInfrastructureUCR, self).__init__(config)

    @property
    def filter_values(self):
        clean_IN_filter_value(self.config, 'awc_id')
        return self.config

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], 'static-infrastructure_form')

    @property
    def filters(self):
        return [
            IN('awc_id', get_INFilter_bindparams('awc_id', self.awcs)),
            EQ('month', 'month')
        ]

    @property
    def group_by(self):
        return [
            'awc_id', 'where_housed', 'provided_building', 'other_building', 'kitchen', 'toilet_facility',
            'type_toilet', 'preschool_kit_available', 'preschool_kit_usable'
        ]

    @property
    def columns(self):
        return [
            DatabaseColumn('awc_id', SimpleColumn('awc_id')),
            DatabaseColumn('where_housed', SimpleColumn('where_housed')),
            DatabaseColumn('provided_building', SimpleColumn('provided_building')),
            DatabaseColumn('other_building', SimpleColumn('other_building')),
            DatabaseColumn('kitchen', SimpleColumn('kitchen')),
            DatabaseColumn('toilet_facility', SimpleColumn('toilet_facility')),
            DatabaseColumn('type_toilet', SimpleColumn('type_toilet')),
            DatabaseColumn('preschool_kit_available', SimpleColumn('preschool_kit_available')),
            DatabaseColumn('preschool_kit_usable', SimpleColumn('preschool_kit_usable'))
        ]
