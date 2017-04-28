from corehq.apps.repeaters.views import AddCaseRepeaterView


class BETSVoucherRepeaterView(AddCaseRepeaterView):
    urlname = 'bets_voucher_repeater'
    page_title = "BETS Vouchers"
    page_name = "BETS Vouchers (voucher case type)"


class BETS180TreatmentRepeaterView(AddCaseRepeaterView):
    urlname = "bets_180_treatment_repeater"
    page_title = "MBBS+ Providers: 6 months (180 days) of private OR govt. FDCs with treatment outcome reported"
    page_name = "MBBS+ Providers: 6 months (180 days) of private OR govt. FDCs with treatment outcome reported (episode case type)"


class BETSDrugRefillRepeaterView(AddCaseRepeaterView):
    urlname = "bets_drug_refill_repeater"
    page_title = "Patients: Cash transfer on subsequent drug refill"
    page_name = "Patients: Cash transfer on subsequent drug refill (voucher case_type)"


class BETSSuccessfulTreatmentRepeaterView(AddCaseRepeaterView):
    urlname = "bets_successful_treatment_repeater"
    page_title = "Patients: Cash transfer on successful treatment completion"
    page_name = "Patients: Cash transfer on successful treatment completion (episode case type)"


class BETSDiagnosisAndNotificationRepeaterView(AddCaseRepeaterView):
    urlname = "bets_diagnosis_and_notification_repeater"
    page_title = "MBBS+ Providers: To provider for diagnosis and notification of TB case"
    page_name = "MBBS+ Providers: To provider for diagnosis and notification of TB case (episode case type)"


class BETSAYUSHReferralRepeaterView(AddCaseRepeaterView):
    urlname = "bets_ayush_referral_repeater"
    page_title = "AYUSH/Other provider: Registering and referral of a presumptive TB case in UATBC/e-Nikshay"
    page_name = "AYUSH/Other provider: Registering and referral of a presumptive TB case in UATBC/e-Nikshay (episode case type)"
