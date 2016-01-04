from corehq.apps.locations.models import Location
from corehq.apps.sms.mixin import PhoneNumberInUseException, VerifiedNumber
from custom.ewsghana.reminders import REGISTER_HELP, REGISTRATION_CONFIRM
from django.contrib.auth.models import User
from corehq.apps.users.models import CommCareUser
from custom.logistics.commtrack import add_location
from custom.ilsgateway.models import ILSGatewayConfig
from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler
from custom.ilsgateway.tanzania.reminders import Languages


class RegistrationHandler(KeywordHandler):
    def help(self):
        self.respond(REGISTER_HELP)

    def _get_facility_location(self, domain, msd_code):
        return Location.by_site_code(domain, msd_code)

    def handle(self):
        words = self.args
        if len(words) < 2 or len(words) > 3:
            self.respond(REGISTER_HELP)
            return

        name = words[0]
        code = words[1]
        params = {
            "msd_code": code
        }
        if not self.user:
            domains = [config.domain for config in ILSGatewayConfig.get_all_configs()]
            for domain in domains:
                loc = self._get_facility_location(domain, code)
                if not loc:
                    continue

                splited_name = name.split(' ', 1)
                first_name = splited_name[0]
                last_name = splited_name[1] if len(splited_name) > 1 else ""
                clean_name = name.replace(' ', '.')
                username = "%s@%s.commcarehq.org" % (clean_name, domain)
                password = User.objects.make_random_password()
                user = CommCareUser.create(domain=domain, username=username, password=password,
                                           commit=False)
                user.first_name = first_name
                user.last_name = last_name

                if len(words) == 3:
                    user.user_data = {
                        'role': words[2]
                    }

                try:
                    user.set_default_phone_number(self.msg.phone_number.replace('', ''))
                    user.save_verified_number(domain, self.msg.phone_number.replace('', ''), True, self.msg.backend_api)
                except PhoneNumberInUseException as e:
                    v = VerifiedNumber.by_phone(self.msg.phone_number, include_pending=True)
                    v.delete()
                    user.save_verified_number(domain, self.msg.phone_number.replace('', ''), True, self.msg.backend_api)
                except CommCareUser.Inconsistent:
                    continue

                user.language = Languages.DEFAULT

                params.update({
                    'sdp_name': loc.name,
                    'contact_name': name
                })

                dm = user.get_domain_membership(domain)
                dm.location_id = loc.location_id
                user.save()
                add_location(user, loc.location_id)

        self.respond(REGISTRATION_CONFIRM, **params)
