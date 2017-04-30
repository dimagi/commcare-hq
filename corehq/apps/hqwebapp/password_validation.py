from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _

from corehq.apps.hqwebapp.const import RESTRICT_USED_PASSWORDS_NUM
from corehq.apps.hqwebapp.models import UsedPasswords
from corehq.apps.hqwebapp.utils import verify_password, hash_password


class UsedPasswordValidator(object):
    def validate(self, password, user):
        used_passwords = UsedPasswords.objects.filter(
            user=user,
        ).order_by('-created_at').all()[:RESTRICT_USED_PASSWORDS_NUM].values_list('password_hash', flat=True)
        used_passwords = list(used_passwords) + [user.password]
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
        UsedPasswords.objects.create(
            user=user,
            password_hash=hash_password(password)
        )

    def get_help_text(self):
        return _("Your password can't be same as last {restricted} passwords.").format(
            restricted=RESTRICT_USED_PASSWORDS_NUM
        )
