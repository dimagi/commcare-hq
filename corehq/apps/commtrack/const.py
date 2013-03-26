
COMMTRACK_USERNAME = 'commtrack-system'

SUPPLY_POINT_CASE_TYPE = 'supply-point'
SUPPLY_POINT_PRODUCT_CASE_TYPE = 'supply-point-product'
REQUISITION_CASE_TYPE = 'requisition'

# supply point products --> supply points and sp product --> requisitions
PARENT_CASE_REF = 'parent'

# http://stackoverflow.com/questions/36932/whats-the-best-way-to-implement-an-enum-in-python
def enum(**enums):
    return type('Enum', (), enums)

RequisitionActions = enum(
    REQUEST='request',
    APPROVAL='approval',
    FILL='fill',
    RECEIPTS='requisition-receipts',
)