from collections import namedtuple
import logging
import csv
from couchdbkit.exceptions import ResourceNotFound
from django.core.management import BaseCommand
from casexml.apps.case.models import CommCareCase
from corehq.apps.hqcase.utils import get_case_by_identifier
from dimagi.utils.couch.database import iter_docs



MOTECH_ID = "fb6e0b19cbe3ef683a10c4c4766a1ef3"


class Command(BaseCommand):
    """
    One time command for cleaning up care-bihar data.
    Takes one argument, the directory containing the three input files.
    """

    cases_to_save = {}

    def get_case(self, case_id):
        return self.cases_to_save.get(case_id) or get_case_by_identifier("care-bihar", case_id)

    def handle(self, *args, **options):
        if len(args) != 1:
            print "Invalid arguments: %s" % str(args)
            return
        dir = args[0]

        # sheet1: update user id for task cases
        with open(dir + '/update_userid.csv') as f:
            reader = csv.reader(f)
            reader.next()
            for row in reader:
                case = self.get_case(row[0])
                if case.user_id != MOTECH_ID:
                    case.user_id = MOTECH_ID
                    self.cases_to_save[case.case_id] = case

        # sheet2: check owner id for task cases
        with open(dir + '/update_ownerid.csv') as f:#blank/None
            reader = csv.reader(f)
            reader.next()
            for row in reader:
                case = self.get_case(row[0])
                owner_id = row[1]
                if case.owner_id != owner_id:
                    case.owner_id = owner_id
                    self.cases_to_save[case.case_id] = case
                    print("Updated case with id " + case.case_id + " to have owner with id " + case.owner_id)

        # sheet3: update cases without types
        with open(dir + '/blank_case_type.csv') as f:
            reader = csv.reader(f)
            reader.next()
            for row in reader:
                case = self.get_case(row[0])
                if case.user_id == MOTECH_ID:
                    case.type = "task"
                    self.cases_to_save[case.case_id] = case
                    print("Case with name " + case.name + " updated to type " + case.type)
                else:
                    print("Type not updated for case with name " + case.name)

        print(str(len(self.cases_to_save)) + " cases to save")
        if len(self.cases_to_save):
            CommCareCase.get_db().bulk_save(self.cases_to_save.values())

        print("Complete.")

