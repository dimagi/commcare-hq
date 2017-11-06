from __future__ import absolute_import
from sqlagg.columns import CountUniqueColumn, SumColumn
from sqlagg.filters import EQ, NOT

from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn
from corehq.apps.userreports.util import get_table_name
from custom.champ.utils import PREVENTION_XMLNS, ENHANCED_PEER_MOBILIZATION, CHAMP_CAMEROON, POST_TEST_XMLNS, \
    ACCOMPAGNEMENT_XMLNS, SUIVI_MEDICAL_XMLNS


class UICFromEPMDataSource(SqlData):

    def __init__(self, config=None):
        config['xmlns'] = PREVENTION_XMLNS
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
            DatabaseColumn('count_uic', CountUniqueColumn('uic'))
        ]


class UICFromCCDataSource(SqlData):

    def __init__(self, config=None):
        config['xmlns'] = POST_TEST_XMLNS
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
            DatabaseColumn('count_uic', CountUniqueColumn('uic'))
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

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], ENHANCED_PEER_MOBILIZATION)

    @property
    def columns(self):
        return [
            DatabaseColumn('target_kp_prev', SumColumn('target_kp_prev')),
            DatabaseColumn('target_htc_tst', SumColumn('target_htc_tst')),
            DatabaseColumn('target_htc_pos', SumColumn('target_htc_pos')),
            DatabaseColumn('target_care_new', SumColumn('target_care_new')),
            DatabaseColumn('target_tx_new', SumColumn('target_tx_new')),
            DatabaseColumn('target_tx_undetect', SumColumn('target_tx_undetect'))
        ]


class HivStatusDataSource(SqlData):

    def __init__(self, config=None):
        config['xmlns'] = POST_TEST_XMLNS
        config['hiv_status'] = 'positive'
        super(HivStatusDataSource, self).__init__(config)

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], CHAMP_CAMEROON)

    @property
    def engine_id(self):
        return 'ucr'

    @property
    def filters(self):
        filters = [EQ('xmlns', 'xmlns'), EQ('hiv_status', 'hiv_status')]
        if 'posttest_date' in self.config and self.config['posttest_date']:
            filters.append(EQ('posttest_date', 'posttest_date'))
        if 'hiv_test_date' in self.config and self.config['hiv_test_date']:
            filters.append(EQ('hiv_test_date', 'hiv_test_date'))
        if 'age_range' in self.config and self.config['age_range']:
            filters.append(EQ('age_range', 'age_range'))
        if 'district' in self.config and self.config['district']:
            filters.append(EQ('district', 'district'))
        if 'mobile_user_group' in self.config and self.config['mobile_user_group']:
            filters.append(EQ('mobile_user_group', 'mobile_user_group'))
        return filters

    @property
    def group_by(self):
        return ['xmlns']

    @property
    def columns(self):
        return [
            DatabaseColumn('positive_hiv_status', CountUniqueColumn('uic'))
        ]


class FormCompletionDataSource(SqlData):

    def __init__(self, config=None):
        config['xmlns'] = ACCOMPAGNEMENT_XMLNS
        super(FormCompletionDataSource, self).__init__(config)

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], CHAMP_CAMEROON)

    @property
    def engine_id(self):
        return 'ucr'

    @property
    def filters(self):
        filters = [EQ('xmlns', 'xmlns')]
        if 'hiv_status' in self.config and self.config['hiv_status']:
            filters.append(EQ('hiv_status', 'hiv_status'))
        if 'client_type' in self.config and self.config['client_type']:
            filters.append(EQ('client_type', 'client_type'))
        if 'age_range' in self.config and self.config['age_range']:
            filters.append(EQ('age_range', 'age_range'))
        if 'district' in self.config and self.config['district']:
            filters.append(EQ('district', 'district'))
        if 'date_handshake' in self.config and self.config['date_handshake']:
            filters.append(EQ('date_handshake', 'date_handshake'))
        if 'mobile_user_group' in self.config and self.config['mobile_user_group']:
            filters.append(EQ('mobile_user_group', 'mobile_user_group'))
        return filters

    @property
    def group_by(self):
        return ['xmlns']

    @property
    def columns(self):
        return [
            DatabaseColumn('form_completion', CountUniqueColumn('uic'))
        ]


class FirstArtDataSource(SqlData):

    def __init__(self, config=None):
        config['xmlns'] = SUIVI_MEDICAL_XMLNS
        config['empty_first_art_date'] = ''
        super(FirstArtDataSource, self).__init__(config)

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], CHAMP_CAMEROON)

    @property
    def engine_id(self):
        return 'ucr'

    @property
    def filters(self):
        filters = [EQ('xmlns', 'xmlns'), NOT(EQ('first_art_date', 'empty_first_art_date'))]
        if 'hiv_status' in self.config and self.config['hiv_status']:
            filters.append(EQ('hiv_status', 'hiv_status'))
        if 'client_type' in self.config and self.config['client_type']:
            filters.append(EQ('client_type', 'client_type'))
        if 'age_range' in self.config and self.config['age_range']:
            filters.append(EQ('age_range', 'age_range'))
        if 'district' in self.config and self.config['district']:
            filters.append(EQ('district', 'district'))
        if 'first_art_date' in self.config and self.config['first_art_date']:
            filters.append(EQ('first_art_date', 'first_art_date'))
        if 'mobile_user_group' in self.config and self.config['mobile_user_group']:
            filters.append(EQ('mobile_user_group', 'mobile_user_group'))
        return filters

    @property
    def group_by(self):
        return ['xmlns']

    @property
    def columns(self):
        return [
            DatabaseColumn('first_art', CountUniqueColumn('uic'))
        ]


class LastVLTestDataSource(SqlData):

    def __init__(self, config=None):
        config['xmlns'] = SUIVI_MEDICAL_XMLNS
        config['empty_date_last_vl_test'] = ''
        super(LastVLTestDataSource, self).__init__(config)

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], CHAMP_CAMEROON)

    @property
    def engine_id(self):
        return 'ucr'

    @property
    def filters(self):
        filters = [EQ('xmlns', 'xmlns'), NOT(EQ('date_last_vi_test', 'empty_date_last_vl_test'))]
        if 'hiv_status' in self.config and self.config['hiv_status']:
            filters.append(EQ('hiv_status', 'hiv_status'))
        if 'client_type' in self.config and self.config['client_type']:
            filters.append(EQ('client_type', 'client_type'))
        if 'age_range' in self.config and self.config['age_range']:
            filters.append(EQ('age_range', 'age_range'))
        if 'district' in self.config and self.config['district']:
            filters.append(EQ('district', 'district'))
        if 'date_last_vi_test' in self.config and self.config['date_last_vi_test']:
            filters.append(EQ('date_last_vi_test', 'date_last_vi_test'))
        if 'undetect_vl' in self.config and self.config['undetect_vl']:
            filters.append(EQ('undetect_vl', 'undetect_vl'))
        if 'mobile_user_group' in self.config and self.config['mobile_user_group']:
            filters.append(EQ('mobile_user_group', 'mobile_user_group'))
        return filters

    @property
    def group_by(self):
        return ['xmlns']

    @property
    def columns(self):
        return [
            DatabaseColumn('last_vl_test', CountUniqueColumn('uic'))
        ]
