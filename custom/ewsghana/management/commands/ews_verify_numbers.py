from django.core.management import BaseCommand
from corehq.apps.sms.mixin import apply_leniency, PhoneNumberInUseException, VerifiedNumber
from corehq.apps.users.models import CommCareUser
from custom.ilsgateway.models import ILSGatewayConfig
from dimagi.utils.decorators.memoized import memoized


TEST_BACKEND = 'MOBILE_BACKEND_TEST'


class Command(BaseCommand):
    """
    Manually test the stock data migration.
    """
    args = '<domain>'

    @memoized
    def _get_logistics_domains(self):
        from custom.ewsghana.models import EWSGhanaConfig
        return ILSGatewayConfig.get_all_enabled_domains() + EWSGhanaConfig.get_all_enabled_domains()

    def _save_verified_number(self, domain, user, connection):
        backend_id = None
        if connection['backend'] == 'message_tester':
            backend_id = TEST_BACKEND
        number = apply_leniency(connection['phone_number'])
        try:
            return user.save_verified_number(domain, number, True, backend_id=backend_id)
        except PhoneNumberInUseException:
            v = VerifiedNumber.by_phone(number, include_pending=True)
            if v.domain in self._get_logistics_domains():
                v.delete()
                return user.save_verified_number(domain, number, True, backend_id=backend_id)

    def check_backend(self, connection, vn):
        if connection['backend'] == 'message_tester' and vn.backend_id != TEST_BACKEND:
            vn.backend_id = TEST_BACKEND
            vn.save()
        if connection['backend'] == 'smsgh' and vn.backend_id is not None:
            vn.backend_id = None
            vn.save()

    def handle(self, domain, *args, **options):

        for sms_user in CommCareUser.by_domain(domain):

            if 'connections' not in sms_user.user_data and sms_user.phone_numbers:
                print "User {} doesn't have connections data point".format(sms_user.get_id)
                continue

            saved_numbers = []
            default_phone_number = None
            for connection in sms_user.user_data.get('connections', []):
                phone_number = apply_leniency(connection['phone_number'])
                try:
                    if phone_number not in sms_user.phone_numbers:
                        # phone number wasn't properly set to user
                        self._save_verified_number(domain, sms_user, connection)
                    else:
                        # otherwise check if number is properly verified
                        vn = VerifiedNumber.by_phone(apply_leniency(phone_number))
                        if not vn or vn.domain != domain:
                            self._save_verified_number(domain, sms_user, connection)
                        else:
                            self.check_backend(connection, vn)

                    if connection['default']:
                        default_phone_number = phone_number
                        saved_numbers = [default_phone_number] + saved_numbers
                    else:
                        saved_numbers.append(phone_number)

                except PhoneNumberInUseException:
                    # Shouldn't happen
                    print "{}: Phone Number in use {}".format(sms_user.get_id, phone_number)

            if set(saved_numbers) != set(sms_user.phone_numbers):
                sms_user.phone_numbers = saved_numbers
                sms_user.save()

            # Sanity check

            should_have = {
                apply_leniency(connection['phone_number'])
                for connection in sms_user.user_data.get('connections', [])
            }

            if set(sms_user.phone_numbers) != should_have:
                print '{}: Wrong phone numbers {} != {}'.format(
                    sms_user.get_id, set(sms_user.phone_numbers), should_have
                )

            if default_phone_number != sms_user.default_phone_number:
                print '{}: Wrong default number {} != {}'.format(
                    sms_user.get_id, default_phone_number, sms_user.default_phone_number
                )
