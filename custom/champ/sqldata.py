from __future__ import absolute_import
from sqlagg.columns import CountUniqueColumn, SumColumn, SimpleColumn
from sqlagg.filters import EQ, NOT, BETWEEN, IN

from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn
from corehq.apps.reports.util import get_INFilter_bindparams
from corehq.apps.userreports.util import get_table_name
from custom.champ.utils import PREVENTION_XMLNS, ENHANCED_PEER_MOBILIZATION, CHAMP_CAMEROON, POST_TEST_XMLNS, \
    ACCOMPAGNEMENT_XMLNS, SUIVI_MEDICAL_XMLNS
from custom.utils.utils import clean_IN_filter_value
from six.moves import filter


class ChampSqlData(SqlData):

    def __init__(self, config=None):
        super(ChampSqlData, self).__init__(config)
        if 'user_id' in self.config and self.config['user_id']:
            clean_IN_filter_value(self.config, 'user_id')


class UICFromEPMDataSource(ChampSqlData):

    def __init__(self, config=None, replace_group_by=None):
        self.replace_group_by = replace_group_by
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
        if (
            'visit_date_start' in self.config and self.config['visit_date_start'] and
            'visit_date_end' in self.config and self.config['visit_date_end']
        ):
            filters.append(BETWEEN('visit_date', 'visit_date_start', 'visit_date_end'))
        if 'type_visit' in self.config and self.config['type_visit']:
            filters.append(EQ('type_visit', 'type_visit'))
        if 'activity_type' in self.config and self.config['activity_type']:
            filters.append(EQ('activity_type', 'activity_type'))
        if 'client_type' in self.config and self.config['client_type']:
            filters.append(EQ('client_type', 'client_type'))
        if 'user_id' in self.config and self.config['user_id']:
            filters.append(IN('user_id', get_INFilter_bindparams('user_id', self.config['user_id'])))
        if 'organization' in self.config and self.config['organization']:
            filters.append(EQ('organization', 'organization'))
        return filters

    @property
    def group_by(self):
        if self.replace_group_by:
            return [self.replace_group_by]
        return ['xmlns']

    @property
    def columns(self):
        return [
            DatabaseColumn('count_uic', CountUniqueColumn('uic'))
        ]


class UICFromCCDataSource(ChampSqlData):

    def __init__(self, config=None, replace_group_by=None):
        self.replace_group_by = replace_group_by
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
        if (
            'posttest_date_start' in self.config and self.config['posttest_date_start'] and
            'posttest_date_end' in self.config and self.config['posttest_date_end']
        ):
            filters.append(BETWEEN('posttest_date', 'posttest_date_start', 'posttest_date_end'))
        if (
            'hiv_test_date_start' in self.config and self.config['hiv_test_date_start'] and
            'hiv_test_date_end' in self.config and self.config['hiv_test_date_end']
        ):
            filters.append(BETWEEN('hiv_test_date', 'hiv_test_date_start', 'hiv_test_date_end'))
        if 'age_range' in self.config and self.config['age_range']:
            filters.append(EQ('age_range', 'age_range'))
        if 'district' in self.config and self.config['district']:
            filters.append(EQ('district', 'district'))
        if 'client_type' in self.config and self.config['client_type']:
            filters.append(EQ('client_type', 'client_type'))
        if 'user_id' in self.config and self.config['user_id']:
            filters.append(IN('user_id', get_INFilter_bindparams('user_id', self.config['user_id'])))
        if 'organization' in self.config and self.config['organization']:
            filters.append(EQ('organization', 'organization'))
        return filters

    @property
    def group_by(self):
        if self.replace_group_by:
            return [self.replace_group_by]
        return ['xmlns']

    @property
    def columns(self):
        return [
            DatabaseColumn('count_uic', CountUniqueColumn('uic'))
        ]


class TargetsDataSource(ChampSqlData):

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
        if 'organization' in self.config and self.config['organization']:
            filters.append(EQ('organization', 'organization'))
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


class HivStatusDataSource(ChampSqlData):

    def __init__(self, config=None, replace_group_by=None):
        self.replace_group_by = replace_group_by
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
        if (
            'posttest_date_start' in self.config and self.config['posttest_date_start'] and
            'posttest_date_end' in self.config and self.config['posttest_date_end']
        ):
            filters.append(BETWEEN('posttest_date', 'posttest_date_start', 'posttest_date_end'))
        if (
            'hiv_test_date_start' in self.config and self.config['hiv_test_date_start'] and
            'hiv_test_date_end' in self.config and self.config['hiv_test_date_end']
        ):
            filters.append(BETWEEN('hiv_test_date', 'hiv_test_date_start', 'hiv_test_date_end'))
        if 'age_range' in self.config and self.config['age_range']:
            filters.append(EQ('age_range', 'age_range'))
        if 'district' in self.config and self.config['district']:
            filters.append(EQ('district', 'district'))
        if 'client_type' in self.config and self.config['client_type']:
            filters.append(EQ('client_type', 'client_type'))
        if 'user_id' in self.config and self.config['user_id']:
            filters.append(IN('user_id', get_INFilter_bindparams('user_id', self.config['user_id'])))
        if 'organization' in self.config and self.config['organization']:
            filters.append(EQ('organization', 'organization'))
        return filters

    @property
    def group_by(self):
        if self.replace_group_by:
            return [self.replace_group_by]
        return ['xmlns']

    @property
    def columns(self):
        return [
            DatabaseColumn('positive_hiv_status', CountUniqueColumn('uic'))
        ]


class FormCompletionDataSource(ChampSqlData):

    def __init__(self, config=None, replace_group_by=None):
        self.replace_group_by = replace_group_by
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
        if 'handshake_status' in self.config and self.config['handshake_status']:
            filters.append(EQ('handshake_status', 'handshake_status'))
        if 'hiv_status' in self.config and self.config['hiv_status']:
            filters.append(EQ('hiv_status', 'hiv_status'))
        if 'client_type' in self.config and self.config['client_type']:
            filters.append(EQ('client_type', 'client_type'))
        if 'age_range' in self.config and self.config['age_range']:
            filters.append(EQ('age_range', 'age_range'))
        if 'district' in self.config and self.config['district']:
            filters.append(EQ('district', 'district'))
        if (
            'date_handshake_start' in self.config and self.config['date_handshake_start'] and
            'date_handshake_end' in self.config and self.config['date_handshake_end']
        ):
            filters.append(BETWEEN('date_handshake', 'date_handshake_start', 'date_handshake_end'))
        if 'user_id' in self.config and self.config['user_id']:
            filters.append(IN('user_id', get_INFilter_bindparams('user_id', self.config['user_id'])))
        if 'organization' in self.config and self.config['organization']:
            filters.append(EQ('organization', 'organization'))
        return filters

    @property
    def group_by(self):
        if self.replace_group_by:
            return [self.replace_group_by]
        return ['xmlns']

    @property
    def columns(self):
        return [
            DatabaseColumn('form_completion', CountUniqueColumn('uic'))
        ]


class FirstArtDataSource(ChampSqlData):

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
        if (
            'first_art_date_start' in self.config and self.config['first_art_date_start'] and
            'first_art_date_end' in self.config and self.config['first_art_date_end']
        ):
            filters.append(BETWEEN('first_art_date', 'first_art_date_start', 'first_art_date_end'))
        if 'user_id' in self.config and self.config['user_id']:
            filters.append(IN('user_id', get_INFilter_bindparams('user_id', self.config['user_id'])))
        if 'organization' in self.config and self.config['organization']:
            filters.append(EQ('organization', 'organization'))
        return filters

    @property
    def group_by(self):
        return ['xmlns']

    @property
    def columns(self):
        return [
            DatabaseColumn('first_art', CountUniqueColumn('uic'))
        ]


class LastVLTestDataSource(ChampSqlData):

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
        filters = [EQ('xmlns', 'xmlns'), NOT(EQ('date_last_vl_test', 'empty_date_last_vl_test'))]
        if 'hiv_status' in self.config and self.config['hiv_status']:
            filters.append(EQ('hiv_status', 'hiv_status'))
        if 'client_type' in self.config and self.config['client_type']:
            filters.append(EQ('client_type', 'client_type'))
        if 'age_range' in self.config and self.config['age_range']:
            filters.append(EQ('age_range', 'age_range'))
        if 'district' in self.config and self.config['district']:
            filters.append(EQ('district', 'district'))
        if (
            'date_last_vl_test_start' in self.config and self.config['date_last_vl_test_start'] and
            'date_last_vl_test_end' in self.config and self.config['date_last_vl_test_end']
        ):
            filters.append(BETWEEN('date_last_vl_test', 'date_last_vl_test_start', 'date_last_vl_test_end'))
        if 'undetect_vl' in self.config and self.config['undetect_vl']:
            filters.append(EQ('undetect_vl', 'undetect_vl'))
        if 'user_id' in self.config and self.config['user_id']:
            filters.append(IN('user_id', get_INFilter_bindparams('user_id', self.config['user_id'])))
        if 'organization' in self.config and self.config['organization']:
            filters.append(EQ('organization', 'organization'))
        return filters

    @property
    def group_by(self):
        return ['xmlns']

    @property
    def columns(self):
        return [
            DatabaseColumn('last_vl_test', CountUniqueColumn('uic'))
        ]


class ChampFilter(SqlData):

    def __init__(self, domain, xmlns, table, column):
        config = {
            'domain': domain,
            'xmlns': xmlns
        }
        self.table = table
        self.column_name = column
        super(ChampFilter, self).__init__(config)

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], self.table)

    @property
    def group_by(self):
        return [self.column_name]

    @property
    def filters(self):
        return [EQ('xmlns', 'xmlns')]

    @property
    def engine_id(self):
        return 'ucr'

    @property
    def columns(self):
        return [
            DatabaseColumn(self.column_name, SimpleColumn(self.column_name))
        ]

    @property
    def data(self):
        data = sorted(filter(bool, self._get_data().keys()))
        options = [{'id': '', 'value': 'All'}] + [
            {'id': x, 'value': x} for x in data
        ]
        return options
