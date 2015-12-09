from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from casexml.apps.case.models import CommCareCase
from corehq.apps.hqcase.dbaccessors import get_cases_in_domain
from corehq.apps.sms.models import CommConnectCase
from corehq.apps.sms.mixin import InvalidFormatException, PhoneNumberInUseException

class Command(BaseCommand):
    args = "<domain1 domain2 ... >"
    help = "Looks for discrepancies between case phone numbers and corresponding verified number entries for all cases in the given domains."
    option_list = BaseCommand.option_list + (
        make_option("--fix",
                    action="store_true",
                    dest="fix",
                    default=False,
                    help="Include this option to automatically fix any discrepancies where possible."),
    )
    
    def handle(self, *args, **options):
        if len(args) == 0:
            raise CommandError("Usage: python manage.py check_case_verified_numbers <domain1 domain2 ...>")

        make_fixes = options["fix"]

        for domain in args:
            print "*** Processing Domain %s ***" % domain
            for case in get_cases_in_domain(domain):
                contact_phone_number = case.get_case_property("contact_phone_number")
                contact_phone_number_is_verified = case.get_case_property("contact_phone_number_is_verified")
                contact_backend_id = case.get_case_property("contact_backend_id")
                contact_ivr_backend_id = case.get_case_property("contact_ivr_backend_id")
                
                contact = CommConnectCase.wrap(case.to_json())
                verified_numbers = contact.get_verified_numbers(include_pending=True)
                
                should_have_entry = contact_phone_number_is_verified and contact_phone_number is not None and contact_phone_number != "" and str(contact_phone_number) != "0" and not case.closed
                has_entry = len(verified_numbers) > 0
                
                if len(verified_numbers) > 1:
                    print "skipping case %s, multiple verified number entries found" % case._id
                    continue
                
                if has_entry:
                    verified_number = sorted(verified_numbers.iteritems())[0][1]
                    if not verified_number.verified:
                        print "skipping case %s, unverified number found" % case._id
                        continue
                
                if has_entry and should_have_entry:
                    if verified_number.phone_number != contact_phone_number or verified_number.backend_id != contact_backend_id or verified_number.ivr_backend_id != contact_ivr_backend_id:
                        print "DISCREPANCY: case %s case properties don't match the verified number entry" % case._id
                        if make_fixes:
                            try:
                                contact.save_verified_number(contact.domain, contact_phone_number, True, contact_backend_id, ivr_backend_id=contact_ivr_backend_id, only_one_number_allowed=True)
                            except (InvalidFormatException, PhoneNumberInUseException):
                                contact.delete_verified_number()
                elif has_entry and not should_have_entry:
                    print "DISCREPANCY: case %s has a verified number but should not" % case._id
                    if make_fixes:
                        contact.delete_verified_number()
                elif not has_entry and should_have_entry:
                    try:
                        contact.verify_unique_number(contact_phone_number)
                    except InvalidFormatException:
                        print "DISCREPANCY: case %s does not have a verified number because number format is invalid" % case._id
                    except PhoneNumberInUseException:
                        print "DISCREPANCY: case %s does not have a verified number because number is already in use" % case._id
                    else:
                        print "DISCREPANCY: case %s does not have a verified number but should" % case._id
                        if make_fixes:
                            contact.save_verified_number(contact.domain, contact_phone_number, True, contact_backend_id, ivr_backend_id=contact_ivr_backend_id, only_one_number_allowed=True)
                else:
                    # Doesn't have an entry, and shouldn't have an entry
                    pass

