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

    def __init__(self):
        self.output_file = None
        self.extra_options = {}

    def case_block(self):
        raise NotImplementedError()

    def update_cases(self, domain, case_type, user_id):
        raise NotImplementedError()

    def find_case_ids_by_type(self, domain, case_type):
        accessor = CaseAccessors(domain)
        case_ids = accessor.get_case_ids_in_domain(case_type)
        print(f"Found {len(case_ids)} {case_type} cases in {domain}")
        return case_ids

    def log_data(self, domain, command, case_type, total_cases, num_updated, errors, loc_id=None):
        if self.output_file is not None:
            with open(self.output_file, "a") as output_file:
                num_case_updated_str = "{} {}: Updated {} out of the {} {} cases".format(domain, command,
                                                                                         num_updated, total_cases,
                                                                                         case_type)
                if loc_id is not None:
                    num_case_updated_str += f" in this location:{loc_id}"
                output_file.write(num_case_updated_str + '\n')
                for error in errors:
                    output_file.write(domain + ": " + error + '\n')

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('case_type')
        parser.add_argument('--username', type=str, default=None)
        parser.add_argument('--and-linked', action='store_true', default=False)
        parser.add_argument('--output-file', type=str, default=None)

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

        self.output_file = options["output_file"]

        options.pop("and_linked")
        options.pop("username")
        options.pop("output_file", None)
        self.extra_options = options

        for domain in sorted(domains):
            print(f"Processing {domain}")
            self.update_cases(domain, case_type, user_id)
