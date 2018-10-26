from __future__ import unicode_literals
REDIS_USED_PASSWORDS_LIST_PREFIX = 'used_passwords_'
REDIS_LOGIN_ATTEMPTS_LIST_PREFIX = 'login_attempts_'
RESTRICT_USED_PASSWORDS_NUM = 3  # passwords inclusive of current password
EXPIRE_PASSWORD_ATTEMPTS_IN = 10  # days
EXPIRE_LOGIN_ATTEMPTS_IN = 3  # days
MOBILE_REQUESTS_TO_TRACK_FOR_REPLAY_ATTACK = [
    'key_server_url',  # login
    'app_aware_restore',  # restore
    'phone_heartbeat',  # heartbeat
]
