import datetime
import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from corehq.apps.hqcase.bulk import SystemFormMeta, update_cases
from corehq.apps.linked_domain.dbaccessors import get_linked_domains
from corehq.form_processor.models import CommCareCase
from corehq.util.log import with_progress_bar


class CaseUpdateCommand(BaseCommand):
    """
        Base class for updating cases of a specific case_type.
        Override all methods that raise NotImplementedError.
    """

    def __init__(self):
        self.extra_options = {}

    @property
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

    def handle(self, domain, case_type, **options):
        # logger.debug will record something to a file but not print it
        self.logger = logging.getLogger(self.logger_name)
        if not settings.UNIT_TESTING:
            self.logger.addHandler(logging.FileHandler(self.logger_name.split(".")[-1] + ".txt"))
        self.logger.setLevel(logging.DEBUG)

        self.logger.debug(f"{datetime.datetime.utcnow()} Starting run: {options}")
        domains = {domain}
        if options.pop("and_linked"):
            domains = domains | {link.linked_domain for link in get_linked_domains(domain)}

        username = options.pop("username")
        self.case_type = case_type
        self.extra_options = options

        for i, domain in enumerate(sorted(domains), start=1):
            case_ids = self.find_case_ids(domain)
            self.logger.debug(f"Found {len(case_ids)} cases in {domain} ({i}/{len(domains)})")
            update_count = update_cases(
                domain=domain,
                update_fn=self.case_blocks,
                case_ids=with_progress_bar(case_ids, oneline=False),
                form_meta=SystemFormMeta.for_script(self.logger_name, username),
            )
            self.logger.debug(f"Made {update_count} updates in {domain} ({i}/{len(domains)})")

        self.logger.debug(f"{datetime.datetime.utcnow()} Script complete")
