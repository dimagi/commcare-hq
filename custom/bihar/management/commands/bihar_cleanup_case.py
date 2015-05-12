import logging
import csv
from django.core.management import BaseCommand
from casexml.apps.case.models import CommCareCase
from dimagi.utils.couch.database import iter_docs

logger = logging.getLogger('case_cleanup')
logger.setLevel('DEBUG')


MOTECH_ID = "fb6e0b19cbe3ef683a10c4c4766a1ef3"

class CaseRow(object):
    headers = ['case_id', 'old_case_type', 'new_case_type',
               'old_owner_id', 'new_owner_id', 'parent_id',
               'parent_owner_id', 'user_id', 'saved']

    save = False

    def __init__(self, case, parent):
        self.case = case
        self.parent = parent
        self.old_type = case.type
        self.old_owner = case.owner_id

    def update_type(self, new_type):
        self.case.type = new_type
        self.save = True

    def update_owner(self, new_owner):
        self.case.owner_id = new_owner
        self.save = True

    def to_row(self):
        return [
            self.case._id,
            self.old_type,
            self.case.type,
            self.old_owner,
            self.case.owner_id,
            self.parent._id if self.parent else 'no_parent',
            self.parent.owner_id if self.parent else 'no_parent',
            self.case.user_id,
            self.save
        ]

class Command(BaseCommand):
    """
    One time command for cleaning up care-bihar data
    """

    def handle(self, *args, **options):
        csv_file = csv.writer(open('bihar_case_cleanup.csv', 'wb'))
        csv_file.writerow(CaseRow.headers)

        blank_case_type_keys = [
            ["all type", "care-bihar", ""],
            ["all type", "care-bihar", None]
        ]
        blank_case_ids = []
        for key in blank_case_type_keys:
            blank_case_ids += [
                c['id'] for c in
                CommCareCase.view(
                    'case/all_cases',
                    startkey=key,
                    endkey=key + [{}],
                    reduce=False,
                    include_docs=False,
                ).all()
            ]

        # task_case_ids = [c['id'] for c in
        #         CommCareCase.get_all_cases("care-bihar", case_type="task")]

        case_ids = set(blank_case_ids)  # | set(task_case_ids)
        to_save = []

        for i, doc in enumerate(iter_docs(CommCareCase.get_db(), case_ids)):
            case = CommCareCase.wrap(doc)

            # if case.type and case.type != "task":
            #     continue

            parent = case.parent
            case_row = CaseRow(case, parent)

            if case.type != 'task':
                if case.user_id == MOTECH_ID:
                    case_row.update_type('task')

            if parent and parent.owner_id != case.owner_id:
                case_row.update_owner(parent.owner_id)

            csv_file.writerow(case_row.to_row())
            #print case_row.to_row()
            if case_row.save:
                to_save.append(case_row.case)

            if len(to_save) > 25:
                CommCareCase.get_db().bulk_save(to_save)
                to_save = []

            if i % 100 == 0:
                logger.info("{current}/{count} cases completed".format(current=i, count=len(case_ids)))

        if to_save:
            CommCareCase.get_db().bulk_save(to_save)
