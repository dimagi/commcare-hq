from __future__ import unicode_literals
SINGLE_SMS_URL = 'http://103.16.59.36/MtSendSMS/SingleSMS.aspx'
LONG_TEXT_MSG_TYPE = '4'
LONG_UNICODE_MSG_TYPE = '5'
SUCCESS_RESPONSE_REGEX = r'^\d+-\d+(,\d+-\d+)*$'
UNRETRYABLE_ERROR_MESSAGES = [
    'Invalid UserName',
    'Invalid Password',
    'Account Blocked',
    'Please Validate IP',
    'Insufficient Funds',
    'SenderID Not Validated',
    'SenderID Not Approved',
]
