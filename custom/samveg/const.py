SAMVEG_DOMAINS = ["samveg", "samveg-quick"]


RCH_BENEFICIARY_IDENTIFIER = 'Rch_id'
SNCU_BENEFICIARY_IDENTIFIER = 'admission_id'
NEWBORN_WEIGHT_COLUMN = 'newborn_weight'
OWNER_NAME = 'owner_name'

REQUIRED_COLUMNS = [
    'name',
    'MobileNo',
    'DIST_NAME',
    'Health_Block',
    'visit_type',
    'owner_name',
]

RCH_REQUIRED_COLUMNS = [
    RCH_BENEFICIARY_IDENTIFIER,
]

SNCU_REQUIRED_COLUMNS = [
    SNCU_BENEFICIARY_IDENTIFIER,
    NEWBORN_WEIGHT_COLUMN,
]

ROW_LIMIT_PER_OWNER_PER_CALL_TYPE = 40
