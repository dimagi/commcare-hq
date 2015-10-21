class UserMigrationMixin(object):
    def get_username(self, ilsgateway_smsuser, username_part=None):
        domain_part = "%s.commcarehq.org" % self.domain

        if not username_part:
            username_part = "%s%d" % (ilsgateway_smsuser.name.strip().replace(' ', '.').lower(),
                                      ilsgateway_smsuser.id)
        return "%s@%s" % (username_part[:(128 - (len(domain_part) + 1))], domain_part), username_part
