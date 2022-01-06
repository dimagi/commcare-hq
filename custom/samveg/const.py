RCH_BENEFICIARY_IDENTIFIER = 'Rch_id'
SNCU_BENEFICIARY_IDENTIFIER = 'admission_id'
OWNER_NAME = 'owner_name'

ROW_LIMIT_PER_OWNER_PER_CALL_TYPE = 40

MANDATORY_COLUMNS = [
    'name',
    'MobileNo',
    'DIST_NAME',
    'Health_Block',
    'visit_type',
    OWNER_NAME
]

RCH_MANDATORY_COLUMNS = [
    RCH_BENEFICIARY_IDENTIFIER,
]

SNCU_MANDATORY_COLUMNS = [
    SNCU_BENEFICIARY_IDENTIFIER,
    'newborn_weight'
]

SAMVEG_DOMAINS = ["samveg", "samveg-quick"]
