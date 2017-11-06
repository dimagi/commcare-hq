from __future__ import absolute_import

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.generic.base import View

from corehq.apps.domain.decorators import login_and_domain_required
from custom.champ.sqldata import TargetsDataSource, UICFromEPMDataSource, UICFromCCDataSource, HivStatusDataSource, \
    FormCompletionDataSource, FirstArtDataSource, LastVLTestDataSource
from custom.champ.utils import PREVENTION_XMLNS, POST_TEST_XMLNS, ACCOMPAGNEMENT_XMLNS, SUIVI_MEDICAL_XMLNS


@method_decorator([login_and_domain_required], name='dispatch')
class PrevisionVsAchievementsView(View):

    def get_target_data(self, domain, request):
        config = {
            'domain': domain,
            'district': request.GET.get('target_district', None),
            'cbo': request.GET.get('cbo', None),
            'clienttype': request.GET.get('clienttype', None),
            'userpl': request.GET.get('userpl', None),
            'fiscal_year': request.GET.get('fiscal_year', None),
        }
        target_data = TargetsDataSource(config=config).data
        return target_data

    def get_kp_prev_achievement(self, domain, request):
        config = {
            'domain': domain,
            'age': request.GET.get('kp_prev_age', None),
            'district': request.GET.get('kp_prev_district', None),
            'visit_date': request.GET.get('kp_prev_visit_date', None),
            'activity_type': request.GET.get('kp_prev_activity_type', None),
            'client_type': request.GET.get('kp_prev_client_type', None),
            'mobile_user_group': request.GET.get('kp_prev_mobile_user_group', None),
        }
        achievement = UICFromEPMDataSource(config=config).data
        return achievement.get(PREVENTION_XMLNS, {}).get('uic', 0)

    def get_htc_tst_achievement(self, domain, request):
        config = {
            'domain': domain,
            'posttest_date': request.GET.get('htc_tst_posttest_date', None),
            'hiv_test_date': request.GET.get('htc_tst_hiv_test_date', None),
            'age_range': request.GET.get('htc_tst_age_range', None),
            'district': request.GET.get('htc_tst_district', None),
            'mobile_user_group': request.GET.get('htc_tst_mobile_user_group', None),
        }
        achievement = UICFromCCDataSource(config=config).data
        return achievement.get(POST_TEST_XMLNS, {}).get('uic', 0)

    def get_htc_pos_achievement(self, domain, request):
        config = {
            'domain': domain,
            'posttest_date': request.GET.get('htc_pos_posttest_date', None),
            'hiv_test_date': request.GET.get('htc_pos_hiv_test_date', None),
            'age_range': request.GET.get('htc_pos_age_range', None),
            'district': request.GET.get('htc_pos_district', None),
            'client_type': request.GET.get('htc_pos_client_type', None),
            'mobile_user_group': request.GET.get('htc_pos_mobile_user_group', None),
        }
        achievement = HivStatusDataSource(config=config).data
        return achievement.get(POST_TEST_XMLNS, {}).get('uic', 0)

    def get_care_new_achivement(self, domain, request):
        config = {
            'domain': domain,
            'hiv_status': request.GET.get('care_new_hiv_status', None),
            'client_type': request.GET.get('care_new_client_type', None),
            'age_range': request.GET.get('care_new_age_range', None),
            'district': request.GET.get('care_new_district', None),
            'date_handshake': request.GET.get('fcare_new_date_handshake', None),
            'mobile_user_group': request.GET.get('care_new_mobile_user_group', None),
        }
        achievement = FormCompletionDataSource(config=config).data
        return achievement.get(ACCOMPAGNEMENT_XMLNS, {}).get('uic', 0)

    def get_tx_new_achivement(self, domain, request):
        config = {
            'domain': domain,
            'hiv_status': request.GET.get('tx_new_hiv_status', None),
            'client_type': request.GET.get('tx_new_client_type', None),
            'age_range': request.GET.get('tx_new_age_range', None),
            'district': request.GET.get('tx_new_district', None),
            'first_art_date': request.GET.get('tx_new_first_art_date', None),
            'mobile_user_group': request.GET.get('tx_new_mobile_user_group', None),
        }
        achievement = FirstArtDataSource(config=config).data
        return achievement.get(SUIVI_MEDICAL_XMLNS, {}).get('uic', 0)

    def get_tx_undetect_achivement(self, domain, request):
        config = {
            'domain': domain,
            'hiv_status': request.GET.get('tx_undetect_hiv_status', None),
            'client_type': request.GET.get('tx_undetect_client_type', None),
            'age_range': request.GET.get('tx_undetect_age_range', None),
            'district': request.GET.get('tx_undetect_district', None),
            'date_last_vi_test': request.GET.get('tx_undetect_date_last_vi_test', None),
            'undetect_vl': request.GET.get('tx_undetect_undetect_vl', None),
            'mobile_user_group': request.GET.get('tx_undetect_mobile_user_group', None),
        }
        achievement = LastVLTestDataSource(config=config).data
        return achievement.get(SUIVI_MEDICAL_XMLNS, {}).get('uic', 0)

    def generate_data(self, domain, request):
        targets = self.get_target_data(domain, request)
        return {
            'chart': [
                {
                    'key': 'Target',
                    'color': 'blue',
                    'values': [
                        {'x': 'KP_PREV', 'y': targets.get('target_kp_prev', 0)},
                        {'x': 'HTC_TST', 'y': targets.get('target_htc_tst', 0)},
                        {'x': 'HTC_POS', 'y': targets.get('target_htc_pos', 0)},
                        {'x': 'CARE_NEW', 'y': targets.get('target_care_new', 0)},
                        {'x': 'TX_NEW', 'y': targets.get('target_tx_new', 0)},
                        {'x': 'TX_UNDETECT', 'y': targets.get('target_tx_undetect', 0)}
                    ]
                },
                {
                    'key': 'Achievements',
                    'color': 'orange',
                    'values': [
                        {'x': 'KP_PREV', 'y': self.get_kp_prev_achievement(domain, request)},
                        {'x': 'HTC_TST', 'y': self.get_htc_tst_achievement(domain, request)},
                        {'x': 'HTC_POS', 'y': self.get_htc_pos_achievement(domain, request)},
                        {'x': 'CARE_NEW', 'y': self.get_care_new_achivement(domain, request)},
                        {'x': 'TX_NEW', 'y': self.get_tx_new_achivement(domain, request)},
                        {'x': 'TX_UNDETECT', 'y': self.get_tx_undetect_achivement(domain, request)}
                    ]
                }
            ]
        }

    def get(self, request, *args, **kwargs):
        domain = self.kwargs['domain']
        return JsonResponse(data=self.generate_data(domain, request))
