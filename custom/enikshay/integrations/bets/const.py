# maps an internal slug to BETS "parent event ID"
BETS_EVENT_IDS = {
    # e-Voucher payout to chemists (reimbursement of drug cost + additional x% top up)
    'chemist_voucher': '101',

    # e-Voucher payout to labs (reimbursement of lab test cost - partial or in full)
    'lab_voucher': '102',

    # To provider for diagnosis and notification of TB case
    'tb_diagnosis': '103',

    # 6 months (180 days) of private OR govt. FDCs with "Treatment Outcome" reported
    'outcome_reported': '104',

    # Registering and referral of a presumptive TB case in UATBC/eNikshay,
    # and patient subsequently gets notified
    'tb_registration': '105',

    # Suspect Registration + Validated diagnostic e-Voucher prior to or on date
    # of treatment initiation
    'suspect_registration': '106',

    # To compounder on case notification
    'case_notification': '107',

    # Honorarium to chemists for dispensing GoI - supplied daily drugs
    'chemist_honorarium': '108',

    # Cash transfer on subsequent drug refill (~at every drug voucher validation,
    # starting after 2nd voucher)
    'drug_refill': '109',

    # Honorarium to public DOT providers
    'provider_honorarium': '110',
}
