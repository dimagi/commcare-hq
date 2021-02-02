from django.core.management.base import BaseCommand

from corehq.apps.linked_domain.dbaccessors import get_linked_domains
from corehq.apps.users.util import SYSTEM_USER_ID
from corehq.apps.users.util import username_to_user_id
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


class CaseUpdateCommand(BaseCommand):
    """
        Base class for updating cases of a specific case_type.
        Override all methods that raise NotImplementedError.
    """

    def case_block(self):
        raise NotImplementedError()

    def update_cases(self, domain, case_type, user_id, active_location):
        raise NotImplementedError()

    def find_case_ids_by_type(self, domain, case_type):
        accessor = CaseAccessors(domain)
        case_ids = accessor.get_case_ids_in_domain(case_type)
        print(f"Found {len(case_ids)} {case_type} cases in {domain}")
        return case_ids

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('case_type')
        parser.add_argument('--username', type=str, default=None)
        parser.add_argument('--and-linked', action='store_true', default=False)

    def handle(self, domain, case_type, **options):
        domains = {domain}
        if options["and_linked"]:
            domains = domains | {link.linked_domain for link in get_linked_domains(domain)}

        if options["username"]:
            user_id = username_to_user_id(options["username"])
            if not user_id:
                raise Exception("The username you entered is invalid")
        else:
            user_id = SYSTEM_USER_ID

        try:
            if options["location"]:
                active_location = options["location"]
            else:
                print("Warning: No active location was entered")
                active_location = None
        except KeyError:
            active_location = None

        for domain in domains:
            print(f"Processing {domain}")
            self.update_cases(domain, case_type, user_id, active_location)
