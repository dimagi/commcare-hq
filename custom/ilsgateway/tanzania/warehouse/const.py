from custom.ilsgateway.models import SupplyPointStatusTypes, SupplyPointStatusValues

NEEDED_STATUS_TYPES = [SupplyPointStatusTypes.DELIVERY_FACILITY,
                       SupplyPointStatusTypes.R_AND_R_FACILITY,
                       SupplyPointStatusTypes.SUPERVISION_FACILITY,
                       SupplyPointStatusTypes.SOH_FACILITY]

NO_PRIMARY_CONTACT = 'no_primary_contact'
PRODUCT_STOCKOUT = 'product_stockout'
RR_NOT_SUBMITTED = 'rr_' + SupplyPointStatusValues.NOT_SUBMITTED
RR_NOT_RESPONDED = 'rr_not_responded'
DELIVERY_NOT_RECEIVED = 'delivery_' + SupplyPointStatusValues.NOT_RECEIVED
DELIVERY_NOT_RESPONDING = 'delivery_not_responding'
SOH_NOT_RESPONDING = 'soh_not_responding'

TEST_REGION_ID = 21
