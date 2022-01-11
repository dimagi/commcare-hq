SAMVEG_DOMAINS = ["samveg", "samveg-quick"]


RCH_BENEFICIARY_IDENTIFIER = 'Rch_id'
SNCU_BENEFICIARY_IDENTIFIER = 'admission_id'
NEWBORN_WEIGHT_COLUMN = 'newborn_weight'

MANDATORY_COLUMNS = [
    'name',
    'MobileNo',
    'DIST_NAME',
    'Health_Block',
    'visit_type',
    'owner_name',
]

RCH_MANDATORY_COLUMNS = [
    RCH_BENEFICIARY_IDENTIFIER,
]

SNCU_MANDATORY_COLUMNS = [
    SNCU_BENEFICIARY_IDENTIFIER,
    NEWBORN_WEIGHT_COLUMN,
]
