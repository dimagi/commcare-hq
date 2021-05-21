from xml.etree import cElementTree as ElementTree

from django.core.management.base import BaseCommand

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.chunked import chunked

from corehq.apps.es import CaseSearchES
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.util import SYSTEM_USER_ID, username_to_user_id
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

BATCH_SIZE = 100
DEVICE_ID = __name__ + ".update_closed"


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--username', type=str, default=None)

    def handle(self, domain, **options):
        if options["username"]:
            user_id = username_to_user_id(options["username"])
            if not user_id:
                raise Exception("The username you entered is invalid")
        else:
            user_id = SYSTEM_USER_ID

        case_ids = CaseSearchES().domain(domain).xpath_query(domain, "closed != ''").values_list("_id", flat=True)
        accessor = CaseAccessors(domain)
        case_blocks = []
        for case in accessor.iter_cases(case_ids):
            case_blocks.append(ElementTree.tostring(CaseBlock.deprecated_init(
                create=False,
                case_id=case.case_id,
                update={"closed": case.closed},
            ).as_xml(), encoding='utf-8').decode('utf-8'))

        total = 0
        for chunk in chunked(case_blocks, BATCH_SIZE):
            submit_case_blocks(chunk, domain, device_id=DEVICE_ID, user_id=user_id)
            total += len(chunk)
            print("Updated {} cases on domain {}".format(total, domain))
        print("Finished. Updated {} cases on domain {}".format(total, domain))
