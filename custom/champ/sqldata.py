from sqlagg.columns import SimpleColumn, CountColumn, CountUniqueColumn, SumColumn
from sqlagg.filters import EQ

from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn
from corehq.apps.userreports.util import get_table_name


ENHANCED_PEER_MOBILIZATION = 'enhanced_peer_mobilization'
CHAMP_CAMEROON = 'champ_cameroon'


class UICFromEPMDataSource(SqlData):

    def __init__(self, config=None):
        config['xmlns'] = 'http://openrosa.org/formdesigner/DF2FBEEA-31DE-4537-9913-07D57591502C'
        super(UICFromEPMDataSource, self).__init__(config)

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], ENHANCED_PEER_MOBILIZATION)

    @property
    def engine_id(self):
        return 'ucr'

    @property
    def filters(self):
        filters = [EQ('xmlns', 'xmlns')]
        if 'age' in self.config and self.config['age']:
            filters.append(EQ('age', 'age'))
        if 'district' in self.config and self.config['district']:
            filters.append(EQ('district', 'district'))
        if 'visit_date' in self.config and self.config['visit_date']:
            filters.append(EQ('visit_date', 'visit_date'))
        if 'type_visit' in self.config and self.config['type_visit']:
            filters.append(EQ('type_visit', 'type_visit'))
        if 'activity_type' in self.config and self.config['activity_type']:
            filters.append(EQ('activity_type', 'activity_type'))
        if 'client_type' in self.config and self.config['client_type']:
            filters.append(EQ('client_type', 'client_type'))
        if 'mobile_user_group' in self.config and self.config['mobile_user_group']:
            filters.append(EQ('mobile_user_group', 'mobile_user_group'))
        return filters

    @property
    def group_by(self):
        return ['xmlns']

    @property
    def columns(self):
        return [
            DatabaseColumn('count_uic', CountUniqueColumn('ui'))
        ]


class UICFromCCDataSource(SqlData):
    def __init__(self, config=None):
        config['xmlns'] = 'http://openrosa.org/formdesigner/E2B4FD32-9A62-4AE8-AAB0-0CE4B8C28AA1'
        super(UICFromCCDataSource, self).__init__(config)

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], CHAMP_CAMEROON)

    @property
    def engine_id(self):
        return 'ucr'

    @property
    def filters(self):
        filters = [EQ('xmlns', 'xmlns')]
        if 'posttest_date' in self.config and self.config['posttest_date']:
            filters.append(EQ('posttest_date', 'posttest_date'))
        if 'hiv_test_date' in self.config and self.config['hiv_test_date']:
            filters.append(EQ('hiv_test_date', 'hiv_test_date'))
        if 'age_range' in self.config and self.config['age_range']:
            filters.append(EQ('age_range', 'age_range'))
        if 'district' in self.config and self.config['district']:
            filters.append(EQ('district', 'district'))
        if 'client_type' in self.config and self.config['client_type']:
            filters.append(EQ('client_type', 'client_type'))
        if 'mobile_user_group' in self.config and self.config['mobile_user_group']:
            filters.append(EQ('mobile_user_group', 'mobile_user_group'))
        return filters

    @property
    def group_by(self):
        return ['xmlns']

    @property
    def columns(self):
        return [
            DatabaseColumn('count_uic', CountUniqueColumn('ui'))
        ]


class TargetsDataSource(SqlData):

    @property
    def engine_id(self):
        return 'ucr'

    @property
    def filters(self):
        filters = []
        if 'district' in self.config and self.config['district']:
            filters.append(EQ('district', 'district'))
        if 'cbo' in self.config and self.config['cbo']:
            filters.append(EQ('cbo', 'cbo'))
        if 'clienttype' in self.config and self.config['clienttype']:
            filters.append(EQ('clienttype', 'clienttype'))
        if 'userpl' in self.config and self.config['userpl']:
            filters.append(EQ('userpl', 'userpl'))
        if 'fiscal_year' in self.config and self.config['fiscal_year']:
            filters.append(EQ('fiscal_year', 'fiscal_year'))
        return filters

    @property
    def group_by(self):
        return []


class TargetsEPMDataSource(TargetsDataSource):


    @property
    def table_name(self):
        return get_table_name(self.config['domain'], ENHANCED_PEER_MOBILIZATION)

    @property
    def columns(self):
        return [
            DatabaseColumn('target_kp_prev', SumColumn('target_kp_prev'))
        ]


class TargetsCCDataSource(TargetsDataSource):


    @property
    def table_name(self):
        return get_table_name(self.config['domain'], CHAMP_CAMEROON)

    @property
    def columns(self):
        return [
            DatabaseColumn('target_htc_tst', SumColumn('target_htc_tst')),
            DatabaseColumn('target_htc_pos', SumColumn('target_htc_pos')),
            DatabaseColumn('target_care_new', SumColumn('target_care_new')),
            DatabaseColumn('target_tx_new', SumColumn('target_tx_new')),
            DatabaseColumn('target_tx_undetect', SumColumn('target_tx_undetect'))
        ]