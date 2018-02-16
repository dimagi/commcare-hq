from __future__ import absolute_import
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _
from dimagi.utils.couch.cache.cache_core import get_redis_client
from custom.nic_compliance.const import (
    RESTRICT_USED_PASSWORDS_NUM,
    REDIS_USED_PASSWORDS_LIST_PREFIX,
    EXPIRE_PASSWORD_ATTEMPTS_IN,
)
from custom.nic_compliance.utils import verify_password, hash_password


class UsedPasswordValidator(object):
    @staticmethod
    def redis_key_for_user(username):
        return REDIS_USED_PASSWORDS_LIST_PREFIX + username

    def get_used_passwords(self, username):
        client = get_redis_client()
        return client.get(self.redis_key_for_user(username), [])

    def validate(self, password, user):
        used_passwords = self.get_used_passwords(user.username) + [user.password]
        for used_password in used_passwords:
            if verify_password(password, used_password):
                raise ValidationError(
                    _("Your password can not be same as last {restricted} passwords.").format(
                        restricted=RESTRICT_USED_PASSWORDS_NUM
                    ),
                    code='password_already_used',
                )

    # hook to password_changed called on all validators when password is changed for a Django User
    def password_changed(self, password, user):
        # store password attempt and retain just RESTRICT_USED_PASSWORDS_NUM attempts
        # Also set expiry time to avoid retaining passwords in redis forever
        client = get_redis_client()
        key_name = self.redis_key_for_user(user.username)
        attempts = client.get(key_name, [])
        attempts.append(hash_password(password))
        client.set(key_name, attempts[-RESTRICT_USED_PASSWORDS_NUM:])
        client.expire(key_name, timedelta(EXPIRE_PASSWORD_ATTEMPTS_IN))

    def get_help_text(self):
        return _("Your password can't be same as last {restricted} passwords.").format(
            restricted=RESTRICT_USED_PASSWORDS_NUM
        )
