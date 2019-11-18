REDIS_USED_PASSWORDS_LIST_PREFIX = 'used_passwords_'
REDIS_LOGIN_ATTEMPTS_LIST_PREFIX = '$$la'
RESTRICT_USED_PASSWORDS_NUM = 3  # passwords inclusive of current password
EXPIRE_PASSWORD_ATTEMPTS_IN = 10  # days
EXPIRE_LOGIN_ATTEMPTS_IN = 3  # days
MOBILE_REQUESTS_TO_TRACK_FOR_REPLAY_ATTACK = [
    'key_server_url',  # login
    'app_aware_restore',  # restore
    'phone_heartbeat',  # heartbeat
]
USERS_TO_TRACK_FOR_REPLAY_ATTACK = [
    'audit.aww1@icds-cas.commcarehq.org',
    'audit.aww2@icds-cas.commcarehq.org',
    'audit.bhd1@icds-cas.commcarehq.org',
    'audit.ls1@icds-cas.commcarehq.org',
    'adhaar.test@icds-cas.commcarehq.org',
]
