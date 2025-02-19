# Each column results in 3 form fields so this must be true:
#   num_columns * 3 < DATA_UPLOAD_MAX_NUMBER_FIELDS
#
# DATA_UPLOAD_MAX_NUMBER_FIELDS defaults to 1000 but there are
# a few other fields as well. Also 300 is a nice round number.
MAX_CASE_IMPORTER_COLUMNS = 300
MAX_CASE_IMPORTER_ROWS = 100_000

# Special case type used to identify when doing a bulk case import
ALL_CASE_TYPE_IMPORT = 'commcare-all-case-types'

# Fields required when importing cases with "payments" case type
MOMO_REQUIRED_PAYMENT_FIELDS = [
    'batch_number',
    'phone_number',
    'email',
    'amount',
    'currency',
    'payee_note',
    'payer_message',
    'user_or_case_id',
]

# Fields that must be absent or blank when importing cases with "payments" case type
MOMO_NO_EDIT_PAYMENT_FIELDS = [
    'payment_verified',
    'payment_submitted',
    'payment_timestamp',
    'payment_status',
]

MOMO_PAYMENT_CASE_TYPE = 'payment'


class LookupErrors(object):
    NotFound, MultipleResults = list(range(2))
