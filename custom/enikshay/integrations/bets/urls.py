from django.conf.urls import url

from corehq.apps.domain.views import AddRepeaterView
from custom.enikshay.integrations.bets.views import (
    update_voucher,
    update_incentive,
    BETSDrugRefillRepeaterView,
    BETS180TreatmentRepeaterView,
    BETSSuccessfulTreatmentRepeaterView,
    BETSDiagnosisAndNotificationRepeaterView,
    BETSAYUSHReferralRepeaterView,
    ChemistBETSVoucherRepeaterView,
    LabBETSVoucherRepeaterView,
)

urlpatterns = [
    url(r'^update_voucher$', update_voucher, name='update_voucher'),
    url(r'^update_incentive$', update_incentive, name='update_incentive'),
    url(
        r'^new_bets_chemist_voucher_repeater$',
        ChemistBETSVoucherRepeaterView.as_view(),
        {'repeater_type': 'ChemistBETSVoucherRepeater'},
        name=ChemistBETSVoucherRepeaterView.urlname
    ),
    url(
        r'^new_bets_lab_voucher_repeater$',
        LabBETSVoucherRepeaterView.as_view(),
        {'repeater_type': 'LabBETSVoucherRepeater'},
        name=LabBETSVoucherRepeaterView.urlname
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
    url(
        r'^location_repeater$',
        AddRepeaterView.as_view(),
        {'repeater_type': 'BETSLocationRepeater'},
        name='bets_location_repeater'
    ),
]
