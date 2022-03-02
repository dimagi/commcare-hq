from casexml.apps.case.mock import CaseBlock

from custom.covid.management.commands.update_cases import CaseUpdateCommand


class Command(CaseUpdateCommand):
    help = "Makes the owner_id for cases blank"

    logger_name = __name__

    def case_blocks(self, case):
        if case.get_case_property('owner_id') == '-':
            return None

        return [CaseBlock(
            create=False,
            case_id=case.case_id,
            update={'owner_id': '-'},
        )]
