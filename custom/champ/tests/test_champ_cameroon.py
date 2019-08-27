from datetime import date

from corehq.apps.userreports.specs import EvaluationContext
from custom.champ.tests.utils import TestDataSourceExpressions
from custom.champ.utils import POST_TEST_XMLNS, ACCOMPAGNEMENT_XMLNS, SUIVI_MEDICAL_XMLNS

CHAMP_CAMEROON_DATA_SOURCE = 'champ_cameroon.json'


class TestEnhancedPeerMobilization(TestDataSourceExpressions):

    data_source_name = CHAMP_CAMEROON_DATA_SOURCE

    def test_champ_cametoon_properties_for_post_test_xmlns(self):
        form = {
            'id': 'form_id',
            'xmlns': POST_TEST_XMLNS,
            'domain': 'champ_cameroon',
            'form': {
                'group': {
                    'age': 12,
                },
                'district': 'test district',
                'visit_date': '2017-01-15',
                'posttest_date': '2017-02-20',
                'age_range': '10-15 yrs',
                'type_visit': 'first visit',
                'date_handshake': '2017-05-03',
                'handshake_status': 'status',
                'meta': {
                    'userID': 'user_id',
                    'timeEnd': '2017-01-31 20:00'
                },
                'seropostive_group': {
                    'first_art_date': '2017-02-03',
                },
                'load': {
                    'uic': 'test uic',
                    'first_art_date': '2017-02-03',
                    'client_type': 'test client',
                },
                'save': {
                    'hiv_status': 'positive',
                },
                'viral_load_group': {
                    'date_last_vl_test': '2017-01-29',
                    'undetect_vl': 'yes',
                }
            }
        }

        case = {
            'district': 'test district',
            'hiv_test_date': '2017-03-15',
        }

        user = {
            'id': 'user_id',
            'domain': 'champ_cameroon',
            'location_id': 'test_location_id'
        }

        self.database.mock_docs = {
            'form_id': form,
            'user_id': user
        }

        xmlns = self.get_expression('xmlns', 'string')
        uic = self.get_expression('uic', 'string')
        district = self.get_expression('district', 'string')
        hiv_test_date = self.get_expression('hiv_test_date', 'date')
        age_range = self.get_expression('age_range', 'string')
        posttest_date = self.get_expression('posttest_date', 'date')
        date_handshake = self.get_expression('date_handshake', 'date')
        first_art_date = self.get_expression('first_art_date', 'string')
        date_last_vl_test = self.get_expression('date_last_vl_test', 'string')
        client_type = self.get_expression('client_type', 'string')
        hiv_status = self.get_expression('hiv_status', 'string')
        handshake_status = self.get_expression('handshake_status', 'string')
        undetect_vl = self.get_expression('undetect_vl', 'string')
        form_completion = self.get_expression('form_completion', 'string')
        user_id = self.get_expression('user_id', 'string')
        htc_month = self.get_expression('htc_month', 'date')
        care_new_month = self.get_expression('care_new_month', 'date')
        organization = self.get_expression('organization', 'string')

        self.assertEquals(
            xmlns(form, EvaluationContext(form, 0)), POST_TEST_XMLNS
        )
        self.assertEquals(
            district(form, EvaluationContext(case, 0)), 'test district'
        )
        self.assertEquals(
            uic(form, EvaluationContext(form, 0)), 'test uic'
        )
        self.assertEquals(
            age_range(form, EvaluationContext(form, 0)), '10-15 yrs'
        )
        self.assertEquals(
            date_handshake(form, EvaluationContext(form, 0)), '2017-05-03'
        )
        self.assertEquals(
            first_art_date(form, EvaluationContext(form, 0)), '2017-02-03'
        )
        self.assertEquals(
            date_last_vl_test(form, EvaluationContext(form, 0)), '2017-01-29'
        )
        self.assertEquals(
            client_type(form, EvaluationContext(case, 0)), 'test client'
        )
        self.assertEquals(
            posttest_date(form, EvaluationContext(form, 0)), '2017-02-20'
        )
        self.assertEquals(
            hiv_status(form, EvaluationContext(form, 0)), 'positive'
        )
        self.assertEquals(
            handshake_status(form, EvaluationContext(form, 0)), 'status'
        )
        self.assertEquals(
            undetect_vl(form, EvaluationContext(form, 0)), 'yes'
        )
        self.assertEquals(
            form_completion(form, EvaluationContext(form, 0)), '2017-01-31 20:00'
        )
        self.assertEquals(
            user_id(form, EvaluationContext(form, 0)), 'user_id'
        )
        self.assertEquals(
            htc_month(form, EvaluationContext(form, 0)), date(2017, 2, 1)
        )
        self.assertEquals(
            care_new_month(form, EvaluationContext(form, 0)), date(2017, 5, 1)
        )
        self.assertEquals(
            organization(form, EvaluationContext(form, 0)), 'test_location_id'
        )
        self.assertEquals(
            hiv_test_date(form, EvaluationContext(case, 0)), '2017-03-15'
        )

    def test_champ_cametoon_properties_for_accompagnement_xmlns(self):
        form = {
            'id': 'form_id',
            'xmlns': ACCOMPAGNEMENT_XMLNS,
            'domain': 'champ_cameroon',
            'form': {
                'group': {
                    'age': 12,
                },
                'district': 'test district',
                'visit_date': '2017-01-15',
                'posttest_date': '2017-02-20',
                'type_visit': 'first visit',
                'date_handshake': '2017-05-03',
                'handshake_status': 'status',
                'meta': {
                    'userID': 'user_id',
                    'timeEnd': '2017-01-31 20:00'
                },
                'seropostive_group': {
                    'first_art_date': '2017-02-03',
                },
                'viral_load_group': {
                    'date_last_vl_test': '2017-01-29',
                    'undetect_vl': 'yes',
                }
            }
        }

        case = {
            'district': 'test district',
            'hiv_test_date': '2017-03-15',
            'name': 'test uic',
            'age_range': '10-15 yrs',
            'client_type': 'test client',
            'hiv_status': 'positive',
        }

        user = {
            'id': 'user_id',
            'domain': 'champ_cameroon',
            'location_id': 'test_location_id'
        }

        self.database.mock_docs = {
            'form_id': form,
            'user_id': user
        }

        xmlns = self.get_expression('xmlns', 'string')
        uic = self.get_expression('uic', 'string')
        district = self.get_expression('district', 'string')
        hiv_test_date = self.get_expression('hiv_test_date', 'date')
        age_range = self.get_expression('age_range', 'string')
        posttest_date = self.get_expression('posttest_date', 'date')
        date_handshake = self.get_expression('date_handshake', 'date')
        first_art_date = self.get_expression('first_art_date', 'string')
        date_last_vl_test = self.get_expression('date_last_vl_test', 'string')
        client_type = self.get_expression('client_type', 'string')
        hiv_status = self.get_expression('hiv_status', 'string')
        handshake_status = self.get_expression('handshake_status', 'string')
        undetect_vl = self.get_expression('undetect_vl', 'string')
        form_completion = self.get_expression('form_completion', 'string')
        user_id = self.get_expression('user_id', 'string')
        htc_month = self.get_expression('htc_month', 'date')
        care_new_month = self.get_expression('care_new_month', 'date')
        organization = self.get_expression('organization', 'string')

        self.assertEquals(
            xmlns(form, EvaluationContext(form, 0)), ACCOMPAGNEMENT_XMLNS
        )
        self.assertEquals(
            district(form, EvaluationContext(case, 0)), 'test district'
        )
        self.assertEquals(
            uic(form, EvaluationContext(case, 0)), 'test uic'
        )
        self.assertEquals(
            age_range(form, EvaluationContext(case, 0)), '10-15 yrs'
        )
        self.assertEquals(
            date_handshake(form, EvaluationContext(form, 0)), '2017-05-03'
        )
        self.assertEquals(
            first_art_date(form, EvaluationContext(form, 0)), '2017-02-03'
        )
        self.assertEquals(
            date_last_vl_test(form, EvaluationContext(form, 0)), '2017-01-29'
        )
        self.assertEquals(
            client_type(form, EvaluationContext(case, 0)), 'test client'
        )
        self.assertEquals(
            posttest_date(form, EvaluationContext(form, 0)), '2017-02-20'
        )
        self.assertEquals(
            hiv_status(form, EvaluationContext(case, 0)), 'positive'
        )
        self.assertEquals(
            handshake_status(form, EvaluationContext(form, 0)), 'status'
        )
        self.assertEquals(
            undetect_vl(form, EvaluationContext(form, 0)), 'yes'
        )
        self.assertEquals(
            form_completion(form, EvaluationContext(form, 0)), '2017-01-31 20:00'
        )
        self.assertEquals(
            user_id(form, EvaluationContext(form, 0)), 'user_id'
        )
        self.assertEquals(
            htc_month(form, EvaluationContext(form, 0)), date(2017, 2, 1)
        )
        self.assertEquals(
            care_new_month(form, EvaluationContext(form, 0)), date(2017, 5, 1)
        )
        self.assertEquals(
            organization(form, EvaluationContext(form, 0)), 'test_location_id'
        )
        self.assertEquals(
            hiv_test_date(form, EvaluationContext(case, 0)), '2017-03-15'
        )

    def test_champ_cametoon_properties_for_survi_medical_xmlns(self):
        form = {
            'id': 'form_id',
            'xmlns': SUIVI_MEDICAL_XMLNS,
            'domain': 'champ_cameroon',
            'form': {
                'group': {
                    'age': 12,
                },
                'district': 'test district',
                'visit_date': '2017-01-15',
                'posttest_date': '2017-02-20',
                'type_visit': 'first visit',
                'age_range': '10-15 yrs',
                'date_handshake': '2017-05-03',
                'handshake_status': 'status',
                'meta': {
                    'userID': 'user_id',
                    'timeEnd': '2017-01-31 20:00'
                },
                'seropostive_group': {
                    'first_art_date': '2017-02-03',
                },
                'load': {
                    'client_type': 'test client',
                    'hiv_status': 'positive',
                },
                'viral_load_group': {
                    'date_last_vl_test': '2017-01-29',
                    'undetect_vl': 'yes',
                }
            }
        }

        case = {
            'district': 'test district',
            'hiv_test_date': '2017-03-15',
            'name': 'test uic',
        }

        user = {
            'id': 'user_id',
            'domain': 'champ_cameroon',
            'location_id': 'test_location_id'
        }

        self.database.mock_docs = {
            'form_id': form,
            'user_id': user
        }

        xmlns = self.get_expression('xmlns', 'string')
        uic = self.get_expression('uic', 'string')
        district = self.get_expression('district', 'string')
        hiv_test_date = self.get_expression('hiv_test_date', 'date')
        age_range = self.get_expression('age_range', 'string')
        posttest_date = self.get_expression('posttest_date', 'date')
        date_handshake = self.get_expression('date_handshake', 'date')
        first_art_date = self.get_expression('first_art_date', 'string')
        date_last_vl_test = self.get_expression('date_last_vl_test', 'string')
        client_type = self.get_expression('client_type', 'string')
        hiv_status = self.get_expression('hiv_status', 'string')
        handshake_status = self.get_expression('handshake_status', 'string')
        undetect_vl = self.get_expression('undetect_vl', 'string')
        form_completion = self.get_expression('form_completion', 'string')
        user_id = self.get_expression('user_id', 'string')
        htc_month = self.get_expression('htc_month', 'date')
        care_new_month = self.get_expression('care_new_month', 'date')
        organization = self.get_expression('organization', 'string')

        self.assertEquals(
            xmlns(form, EvaluationContext(form, 0)), SUIVI_MEDICAL_XMLNS
        )
        self.assertEquals(
            district(form, EvaluationContext(case, 0)), 'test district'
        )
        self.assertEquals(
            uic(form, EvaluationContext(case, 0)), 'test uic'
        )
        self.assertEquals(
            age_range(form, EvaluationContext(form, 0)), '10-15 yrs'
        )
        self.assertEquals(
            date_handshake(form, EvaluationContext(form, 0)), '2017-05-03'
        )
        self.assertEquals(
            first_art_date(form, EvaluationContext(form, 0)), '2017-02-03'
        )
        self.assertEquals(
            date_last_vl_test(form, EvaluationContext(form, 0)), '2017-01-29'
        )
        self.assertEquals(
            client_type(form, EvaluationContext(case, 0)), 'test client'
        )
        self.assertEquals(
            posttest_date(form, EvaluationContext(form, 0)), '2017-02-20'
        )
        self.assertEquals(
            hiv_status(form, EvaluationContext(case, 0)), 'positive'
        )
        self.assertEquals(
            handshake_status(form, EvaluationContext(form, 0)), 'status'
        )
        self.assertEquals(
            undetect_vl(form, EvaluationContext(form, 0)), 'yes'
        )
        self.assertEquals(
            form_completion(form, EvaluationContext(form, 0)), '2017-01-31 20:00'
        )
        self.assertEquals(
            user_id(form, EvaluationContext(form, 0)), 'user_id'
        )
        self.assertEquals(
            htc_month(form, EvaluationContext(form, 0)), date(2017, 2, 1)
        )
        self.assertEquals(
            care_new_month(form, EvaluationContext(form, 0)), date(2017, 5, 1)
        )
        self.assertEquals(
            organization(form, EvaluationContext(form, 0)), 'test_location_id'
        )
        self.assertEquals(
            hiv_test_date(form, EvaluationContext(case, 0)), '2017-03-15'
        )
