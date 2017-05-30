import re

VERTEX_URL = "https://www.smsjust.com/sms/user/urlsms.php"
SUCCESS_RESPONSE_REGEX = r'^(\d+)-(20\d{2})_(\d{2})_(\d{2})$'  # 570737298-2017_05_27
SUCCESS_RESPONSE_REGEX_MATCHER = re.compile(SUCCESS_RESPONSE_REGEX)
TEXT_MSG_TYPE = 'TXT'
UNICODE_MSG_TYPE = 'UNI'
