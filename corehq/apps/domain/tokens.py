from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import base36_to_int

from corehq.apps.users.models import CouchUser


class CustomPasswordResetTokenGenerator(PasswordResetTokenGenerator):
    @staticmethod
    def _get_timestamp_from_token(token):
        ts_b36, _ = token.split("-")
        return base36_to_int(ts_b36)

    def make_token(self, user):
        token = super().make_token(user)
        ts = self._get_timestamp_from_token(token)
        couch_user = CouchUser.from_django_user(user)
        couch_user.last_password_reset_request_token_ts = ts
        couch_user.save()
        return token

    def check_token(self, user, token):
        token_status = super().check_token(user, token)
        if token_status is False:
            return token_status
        ts = self._get_timestamp_from_token(token)
        couch_user = CouchUser.from_django_user(user)
        # TODO Remove the first check below in the second stage of deployment
        if couch_user.last_password_reset_request_token_ts and\
                couch_user.last_password_reset_request_token_ts != ts:
            return False
        return True


custom_password_reset_token_generator = CustomPasswordResetTokenGenerator()
