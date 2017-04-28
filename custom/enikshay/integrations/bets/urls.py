from django.conf.urls import url

from custom.enikshay.integrations.bets.views import (
    BETSVoucherRepeaterView,
    BETSDrugRefillRepeaterView,
    BETS180TreatmentRepeaterView,
    BETSSuccessfulTreatmentRepeaterView,
    BETSDiagnosisAndNotificationRepeaterView,
    BETSAYUSHReferralRepeaterView,
)

urlpatterns = [
    url(
        r'^new_bets_voucher_repeater$',
        BETSVoucherRepeaterView.as_view(),
        {'repeater_type': 'BETSVoucherRepeater'},
        name=BETSVoucherRepeaterView.urlname
    ),
    url(
        r'^new_bets_180_treatment_repeater$',
        BETS180TreatmentRepeaterView.as_view(),
        {'repeater_type': 'BETS180TreatmentRepeater'},
        name=BETS180TreatmentRepeaterView.urlname
    ),
    url(
        r'^new_bets_drg_refill_repeater$',
        BETSDrugRefillRepeaterView.as_view(),
        {'repeater_type': 'BETSDrugRefillRepeater'},
        name=BETSDrugRefillRepeaterView.urlname
    ),
    url(
        r'^new_bets_successful_treatment_repeater$',
        BETSSuccessfulTreatmentRepeaterView.as_view(),
        {'repeater_type': 'BETSSuccessfulTreatmentRepeater'},
        name=BETSSuccessfulTreatmentRepeaterView.urlname
    ),
    url(
        r'^new_bets_diagnosis_and_notification_repeater$',
        BETSDiagnosisAndNotificationRepeaterView.as_view(),
        {'repeater_type': 'BETSDiagnosisAndNotificationRepeater'},
        name=BETSDiagnosisAndNotificationRepeaterView.urlname
    ),
    url(
        r'^new_bets_ayush_referral_repeater$',
        BETSAYUSHReferralRepeaterView.as_view(),
        {'repeater_type': 'BETSAYUSHReferralRepeater'},
        name=BETSAYUSHReferralRepeaterView.urlname
    ),
]
