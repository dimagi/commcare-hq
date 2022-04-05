from xml.etree import cElementTree as ElementTree

from casexml.apps.case.mock import CaseBlock
from django.core.exceptions import ValidationError

from corehq.apps.users.util import normalize_username
from corehq.apps.users.util import username_to_user_id
from custom.covid.management.commands.update_cases import CaseUpdateCommand


class Command(CaseUpdateCommand):
    help = "Updates checkin cases to hold the userid of the mobile worker that the checkin case is associated with"

    logger_name = __name__

    def case_blocks(self, case):
        username_of_associated_mobile_workers = case.get_case_property('username')
        try:
            normalized_username = normalize_username(username_of_associated_mobile_workers, case.domain)
        except ValidationError:
            self.logger.error("ValidationError: invalid username:{} associated with "
                         "case:{}".format(case.get_case_property('username'), case.case_id))
            return None
        user_id_of_mobile_worker = username_to_user_id(normalized_username)
        if user_id_of_mobile_worker:
            return [CaseBlock(
                create=False,
                case_id=case.case_id,
                update={'hq_user_id': user_id_of_mobile_worker},
            )]
