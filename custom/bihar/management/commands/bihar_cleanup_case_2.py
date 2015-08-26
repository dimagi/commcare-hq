import csv
import os
from xml.etree import ElementTree
from couchdbkit.exceptions import ResourceNotFound
from django.core.management import BaseCommand
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.xml import V2
from corehq.apps.hqcase.utils import submit_case_blocks
from dimagi.utils.chunked import chunked

CHUNK_SIZE = 100

MOTECH_ID = "fb6e0b19cbe3ef683a10c4c4766a1ef3"


class CaseToUpdate(object):
    def __init__(self, case):
        self.case = case
        self.new_owner_id = None
        self.new_type = None


class Command(BaseCommand):
    """
    One time command for cleaning up care-bihar data.
    Takes one argument, the directory containing the three input files.
    """

    cases_to_update = {}

    def get_case_to_update(self, case_id):
        case = self.cases_to_update.get(case_id)
        if case:
            return case
        else:
            try:
                case = CommCareCase.get(case_id)
            except ResourceNotFound:
                print "** Error: could not find case with id " + case_id

        return CaseToUpdate(case)
    
    def update_cases(self):
        print("{} cases to update".format(len(self.cases_to_update)))
        if not self.cases_to_update:
            return

        def to_xml(to_update):
            caseblock = CaseBlock(
                create=False,
                case_id=to_update.case.case_id,
                version=V2,
                user_id=MOTECH_ID,
                owner_id=to_update.new_owner_id or CaseBlock.undefined,
                case_type=to_update.new_type or CaseBlock.undefined,
            )

            return ElementTree.tostring(caseblock.as_xml())

        progress = 0
        total = len(self.cases_to_update)
        for chunk in chunked(self.cases_to_update.values(), CHUNK_SIZE):
            case_blocks = map(to_xml, chunk)
            submit_case_blocks(case_blocks, self.domain, user_id=MOTECH_ID)
            progress += len(case_blocks)
            print "Updated {} of {} cases".format(progress, total)

    def handle(self, *args, **options):
        if len(args) != 2:
            print "Invalid arguments. Expecting domain and path to folder. Got: %s" % str(args)
            return
        self.domain = args[0]
        dir = args[1]

        # sheet1: update user id for task cases
        if os.path.exists(dir + '/update_userid.csv'):
            with open(dir + '/update_userid.csv') as f:
                reader = csv.reader(f)
                reader.next()
                for row in reader:
                    case_id = row[0]
                    to_update = self.get_case_to_update(case_id)
                    if to_update and to_update.case.user_id != MOTECH_ID:
                        # all updated cases us the MOTECH user ID
                        self.cases_to_update[case_id] = to_update

        # sheet2: check owner id for task cases
        if os.path.exists(dir + '/update_ownerid.csv'):
            with open(dir + '/update_ownerid.csv') as f:
                reader = csv.reader(f)
                reader.next()
                for row in reader:
                    case_id = row[0]
                    to_update = self.get_case_to_update(case_id)
                    owner_id = row[1]
                    if to_update and to_update.case.owner_id != owner_id:
                        to_update.new_owner_id = owner_id
                        self.cases_to_update[case_id] = to_update
                        print("Updated case with id " + to_update.case.case_id + " to have owner with id " + to_update.case.owner_id)

        # sheet3: update cases without types
        if os.path.exists(dir + '/blank_case_type.csv'):
            with open(dir + '/blank_case_type.csv') as f:
                reader = csv.reader(f)
                reader.next()
                for row in reader:
                    case_id = row[0]
                    to_update = self.get_case_to_update(case_id)
                    if to_update:
                        if to_update.case.user_id == MOTECH_ID:
                            to_update.new_type = "task"
                            self.cases_to_update[case_id] = to_update
                            print("Case '{}' updated from '{}'".format(case_id, to_update.case.type))
                        else:
                            print("Type not updated for case " + case_id)

        self.update_cases()

        print("Complete.")
