from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import SQLLocation
from corehq.apps.sms.api import send_sms_to_verified_number
from corehq.util.translation import localize
from dimagi.utils.decorators.memoized import memoized


class KeywordHandler(object):

    def __init__(self, user, domain, args, msg, verified_contact):
        self.user = user
        self.domain = domain
        self.args = args
        self.verified_contact = verified_contact
        self.msg = msg

    @property
    @memoized
    def domain_object(self):
        return Domain.get_by_name(self.domain)

    @property
    @memoized
    def sql_location(self):
        location = self.user.location

        if location:
            return location.sql_location

        if not self.args:
            return

        try:
            return SQLLocation.objects.get(domain=self.domain, site_code=self.args[0])
        except SQLLocation.DoesNotExist:
            return

    @property
    def location_id(self):
        return self.sql_location.location_id if self.sql_location else None

    @property
    def location_products(self):
        return self.sql_location._products.all() if self.sql_location else []

    def handle(self):
        raise NotImplementedError("Not implemented yet")

    def help(self):
        raise NotImplementedError("Not implemented yet")

    def respond(self, message, **kwargs):
        owner = self.verified_contact.owner
        with localize(owner.get_language_code()):
            send_sms_to_verified_number(self.verified_contact, unicode(message % kwargs))
