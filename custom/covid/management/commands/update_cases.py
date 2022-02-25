import datetime
import logging

from django.core.management.base import BaseCommand

from corehq.apps.hqcase.bulk import SystemFormMeta, update_cases
from corehq.apps.linked_domain.dbaccessors import get_linked_domains
from corehq.apps.users.util import SYSTEM_USER_ID, username_to_user_id, user_id_to_username
from corehq.form_processor.models import CommCareCase
from corehq.util.log import with_progress_bar


class CaseUpdateCommand(BaseCommand):
    """
        Base class for updating cases of a specific case_type.
        Override all methods that raise NotImplementedError.
    """

    def __init__(self):
        self.extra_options = {}

    def logger_name(self):
        """
        Typically __name__
        """
        raise NotImplementedError()

    def case_blocks(self, case):
        """
        Return a list of CaseBlock updates, or None if no updates are needed.
        """
        raise NotImplementedError()

    def find_case_ids(self, domain):
        return CommCareCase.objects.get_case_ids_in_domain(domain, self.case_type)

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('case_type')
        parser.add_argument('--username', type=str, default=None)
        parser.add_argument('--and-linked', action='store_true', default=False)
        parser.add_argument('--throttle-secs', type=float, default=0)

    def handle(self, domain, case_type, **options):
        # logger.debug will record something to a file but not print it
        self.logger = logging.getLogger(self.logger_name())
        self.logger.addHandler(logging.FileHandler(self.logger_name().split(".")[-1] + ".txt"))
        self.logger.setLevel(logging.DEBUG)

        self.logger.debug(f"{datetime.datetime.utcnow()} Starting run: {options}")
        domains = {domain}
        if options.pop("and_linked", False):
            domains = domains | {link.linked_domain for link in get_linked_domains(domain)}

        username = options.pop("username", None)
        if username is not None:
            user_id = username_to_user_id(options["username"])
            if not user_id:
                raise Exception("The username you entered is invalid")
        else:
            user_id = SYSTEM_USER_ID

        self.case_type = case_type
        self.throttle_secs = options.pop("throttle_secs", None)

        self.extra_options = options

        username = user_id_to_username(user_id)
        for i, domain in enumerate(sorted(domains), start=1):
            case_ids = self.find_case_ids(domain)
            self.logger.debug(f"Found {len(case_ids)} cases in {domain} ({i}/{len(domains)})")
            update_count = update_cases(
                domain=domain,
                update_fn=self.case_blocks,
                case_ids=with_progress_bar(case_ids, oneline=False),
                form_meta=SystemFormMeta.for_script(self.logger_name(), username),
                throttle_secs=self.throttle_secs,
            )
            self.logger.debug(f"Made {update_count} updates in {domain} ({i}/{len(domains)})")

        self.logger.debug(f"{datetime.datetime.utcnow()} Script complete")
