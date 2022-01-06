RCH_BENEFICIARY_IDENTIFIER = 'Rch_id'
SNCU_BENEFICIARY_IDENTIFIER = 'admission_id'

MANDATORY_COLUMNS = [
    'name',
    'MobileNo',
    'DIST_NAME',
    'Health_Block',
    'visit_type',
    'owner_name'
]

RCH_MANDATORY_COLUMNS = [
    RCH_BENEFICIARY_IDENTIFIER,
]

SNCU_MANDATORY_COLUMNS = [
    SNCU_BENEFICIARY_IDENTIFIER,
    'newborn_weight'
]

SAMVEG_DOMAINS = ["samveg"]
