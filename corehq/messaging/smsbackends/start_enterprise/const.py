SINGLE_SMS_URL = 'http://174.143.34.193/MtSendSMS/SingleSMS.aspx'
LONG_TEXT_MSG_TYPE = '4'
LONG_UNICODE_MSG_TYPE = '5'
SUCCESS_RESPONSE_REGEX = '^\d+-\d+$'
UNRETRYABLE_ERROR_MESSAGES = [
    'Invalid UserName',
    'Invalid Password',
    'Account Blocked',
    'Please Validate IP',
    'Insufficient Funds',
    'SenderID Not Validated',
    'SenderID Not Approved',
]
