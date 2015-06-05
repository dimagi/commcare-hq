from collections import namedtuple
import logging
import csv
from couchdbkit.exceptions import ResourceNotFound
from django.core.management import BaseCommand
from casexml.apps.case.models import CommCareCase
from dimagi.utils.couch.database import iter_docs

logger = logging.getLogger('case_cleanup')
logger.setLevel('DEBUG')


MOTECH_ID = "fb6e0b19cbe3ef683a10c4c4766a1ef3"


class Command(BaseCommand):
    """
    One time command for cleaning up care-bihar data
    """

    def handle(self, *args, **options):
        case_type_keys = [
                ["all type", "care-bihar", "task"],
                ["all type", "care-bihar", ""],
                ["all type", "care-bihar", None]
            ]
        cases = []
        for key in case_type_keys:
            cases += CommCareCase.view(
                'case/all_cases',
                startkey=key,
                endkey=key + [{}],
                reduce=False,
                include_docs=False,
            ).all()
        cases_by_id = {case.id: case for case in cases}
        cases_to_save = set()

        # sheet1: update user id for task cases
        with open('update_userid.csv') as f:
            reader = csv.reader(f)
            reader.next()
            for row in reader:
                case = cases_by_id[row[0]]
                case.user_id == MOTECH_ID
                cases_to_save.add(case.id)

        # sheet2: check owner id for task cases
        with open('blank_case_type.csv') as f:
            reader = csv.reader(f)
            reader.next()
            for row in reader:
                case = cases_by_id[row[0]]
                owner_id = row[1]
                if case.owner_id != owner_id:
                    case.owner_id = owner_id
                    cases_to_save.add(case.id)
                    logger.info("Updated case with id " + case.id + " to have owner with id " + case.owner_id)

        # sheet3: update cases without types
        with open('update_ownerid.csv') as f:#blank/None
            reader = csv.reader(f)
            reader.next()
            for row in reader:
                case = cases_by_id[row[0]]
                if case.last_submitter == MOTECH_ID:
                    case.type = "task"
                    cases_to_save.add(case.id)
                logger.info("Case with name " + case.name + " is now of type " + case.type)

        logger.info(len(cases_to_save) + " cases to save")
        if len(cases_to_save):
            CommCareCase.get_db().bulk_save(cases_to_save)

        logger.info("Complete.")
