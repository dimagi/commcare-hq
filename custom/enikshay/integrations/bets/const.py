# BETS event names

# Patients: Cash transfer on successful treatment completion
# (* trigger - updating of 'Treatment Outcome' for an episode)
SUCCESSFUL_TREATMENT_EVENT = '104'

# e-Voucher payout to chemists (reimbursement of drug cost + additional x% top up)
CHEMIST_VOUCHER_EVENT = '101'

# e-Voucher payout to labs (reimbursement of lab test cost - partial or in full)
LAB_VOUCHER_EVENT = '102'

# To provider for diagnosis and notification of TB case
DIAGNOSIS_AND_NOTIFICATION_EVENT = '103'

# 6 months (180 days) of private OR govt. FDCs with "Treatment Outcome" reported
TREATMENT_180_EVENT = '104'

# Registering and referral of a presumptive TB case in UATBC/eNikshay,
# and patient subsequently gets notified
AYUSH_REFERRAL_EVENT = '105'

# Suspect Registration + Validated diagnostic e-Voucher prior to or on date
# of treatment initiation
SUSPECT_REGISTRATION_EVENT = '106'

# To compounder on case notification
COMPOUNDER_NOTIFICATION_EVENT = '107'

# Honorarium to chemists for dispensing GoI - supplied daily drugs
CHEMIST_HONORARIUM_EVENT = '108'

# Cash transfer on subsequent drug refill (~at every drug voucher validation,
# starting after 2nd voucher)
DRUG_REFILL_EVENT = '109'

# Honorarium to public DOT providers
PROVIDER_HONORARIUM = '110'

BETS_EVENT_IDS = [
    CHEMIST_VOUCHER_EVENT,
    LAB_VOUCHER_EVENT,
    DIAGNOSIS_AND_NOTIFICATION_EVENT,
    TREATMENT_180_EVENT,
    AYUSH_REFERRAL_EVENT,
    SUSPECT_REGISTRATION_EVENT,
    COMPOUNDER_NOTIFICATION_EVENT,
    CHEMIST_HONORARIUM_EVENT,
    DRUG_REFILL_EVENT,
    PROVIDER_HONORARIUM,
]

LOCATION_TYPE_MAP = {
    "pcc": "chemist",
    "pcp": "mbbs",
    "plc": "lab",
    "pac": "ayush_other",
    # TODO: ?? -> dots_provider
    # TODO: ?? -> compounder
}

TOTAL_DAY_THRESHOLDS = [30, 60, 90, 120]
