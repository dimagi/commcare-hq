EVENT_INCOMING = "incoming_message"
MESSAGE_TYPE_SMS = "sms"
MESSAGE_TYPE_MMS = "mms"
MESSAGE_TYPE_USSD = "ussd"
MESSAGE_TYPE_CALL = "call"

IGNORED = 'ignored'
RECEIVED = 'received'
FAILED = 'failed'
FAILED_QUEUED = 'failed_queued'
CANCELLED = 'cancelled'
DELIVERED = 'delivered'
NOT_DELIVERED = 'not_delivered'

TELERIVIT_FAILED_STATUSES = [
    IGNORED,
    FAILED,
    FAILED_QUEUED,
    CANCELLED,
    NOT_DELIVERED
]
