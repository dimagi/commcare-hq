from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from corehq.apps.sms.mixin import VerifiedNumber
from corehq.apps.users.models import CouchUser
from corehq.apps.reminders.util import (get_verified_number_for_recipient_old,
    get_verified_number_for_recipient)


class Command(BaseCommand):
    args = ""
    help = "Update default phone number based on new methodology."
    option_list = BaseCommand.option_list + (
        make_option("--fix",
                    action="store_true",
                    dest="fix",
                    default=False,
                    help="Include this option to automatically update the default phone numbers."),
    )

    def phones_are_strings(self, user):
        for phone_number in user.phone_numbers:
            if not isinstance(phone_number, basestring):
                return False
        return True

    def handle(self, *args, **options):
        # This is ok, there's only like 50k of these and we're only querying ids
        vns = VerifiedNumber.view(
            'phone_numbers/verified_number_by_owner_id',
            include_docs=False
        ).all()

        # Convert to a dict of {owner id: count of total numbers}
        owners = {}
        for vn in vns:
            owner_id = vn['key']
            if owner_id in owners:
                owners[owner_id] += 1
            else:
                owners[owner_id] = 1

        # Convert to a list of owner ids that have more than one VerifiedNumber
        # (excluding pending numbers)
        mult_list = []
        for owner_id, count in owners.iteritems():
            if count > 1:
                owner_vns = VerifiedNumber.view(
                    'phone_numbers/verified_number_by_owner_id',
                    key=owner_id,
                    include_docs=True
                ).all()
                owner_vns = [vn for vn in owner_vns if vn.verified]
                if len(owner_vns) > 1:
                    mult_list.append(owner_id)

        # If the old methodology's preferred number doesn't match the
        # new one, report it here. Only fix it if options['fix'] is True
        for owner_id in mult_list:
            user = CouchUser.get_by_user_id(owner_id)
            if not user:
                print 'ERROR: User not found: %s' % owner_id
                continue
            if not self.phones_are_strings(user):
                print 'ERROR: Phone numbers should be strings: %s' % owner_id
                continue
            preferred_old_vn = get_verified_number_for_recipient_old(user)
            preferred_new_vn = get_verified_number_for_recipient(user)

            if preferred_old_vn._id != preferred_new_vn._id:
                print "Need to change %s %s from %s to %s" % (
                    user.domain,
                    owner_id,
                    preferred_new_vn.phone_number,
                    preferred_old_vn.phone_number,
                )
                if preferred_old_vn.phone_number not in user.phone_numbers:
                    print 'ERROR: Phone numbers are out of sync: %s' % owner_id
                    continue
                if options.get('fix', False):
                    print "  fixing..."
                    user.set_default_phone_number(preferred_old_vn.phone_number)
