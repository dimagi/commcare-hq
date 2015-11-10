from custom.logistics.utils import get_username_for_user


class UserMigrationMixin(object):
    def get_username(self, ilsgateway_smsuser, username_part=None):
        return get_username_for_user(self.domain, ilsgateway_smsuser, username_part)
