from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from sqlagg.columns import SimpleColumn
from sqlagg.filters import EQ, IN
from sqlagg.sorting import OrderBy

from corehq.apps.reports.sqlreport import DatabaseColumn
from corehq.apps.reports.util import get_INFilter_bindparams
from corehq.apps.userreports.util import get_table_name
from custom.icds_reports.sqldata.base import IcdsSqlData
from custom.utils.utils import clean_IN_filter_value


class VHNDFormUCR(IcdsSqlData):
    def __init__(self, config):
        self.awcs = config['awc_id']
        super(VHNDFormUCR, self).__init__(config)

    @property
    def filter_values(self):
        clean_IN_filter_value(self.config, 'awc_id')
        return self.config

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], 'static-vhnd_form')

    @property
    def filters(self):
        return [
            IN('awc_id', get_INFilter_bindparams('awc_id', self.awcs)),
            EQ('month', 'month')
        ]

    @property
    def group_by(self):
        return ['awc_id', 'submitted_on', 'vhsnd_date_past_month', 'local_leader', 'aww_present']

    @property
    def order_by(self):
        return [OrderBy('submitted_on')]

    @property
    def columns(self):
        return [
            DatabaseColumn('awc_id', SimpleColumn('awc_id')),
            DatabaseColumn('vhsnd_date_past_month', SimpleColumn('vhsnd_date_past_month')),
            DatabaseColumn('local_leader', SimpleColumn('local_leader')),
            DatabaseColumn('aww_present', SimpleColumn('aww_present'))
        ]
