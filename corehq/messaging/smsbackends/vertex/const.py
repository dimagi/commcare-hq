from __future__ import absolute_import
from __future__ import unicode_literals
import re

VERTEX_URL = "https://www.smsjust.com/sms/user/urlsms.php"
SUCCESS_RESPONSE_REGEX = r'^(\d+)-(20\d{2})_(\d{2})_(\d{2})$'  # 570737298-2017_05_27
SUCCESS_RESPONSE_REGEX_MATCHER = re.compile(SUCCESS_RESPONSE_REGEX)
TEXT_MSG_TYPE = 'TXT'
UNICODE_MSG_TYPE = 'UNI'
GATEWAY_ERROR_MESSAGE_REGEX = r'^(ES[\d]{4})?(.*)$'
GATEWAY_ERROR_MESSAGE_REGEX_MATCHER = re.compile(GATEWAY_ERROR_MESSAGE_REGEX)
INCORRECT_MOBILE_NUMBER_CODE = 'ES1009'
GATEWAY_ERROR_CODES = [
    INCORRECT_MOBILE_NUMBER_CODE,
    'ES1001',
    'ES1004',
    'ES1013',
    'ES1002',
    'ES1007',
]
GATEWAY_ERROR_MESSAGES = [
    'Message is blank',
    'Account is Expire',
    'You have Exceeded your SMS Limit.'
]
