import logging
import csv
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
        csv_file = csv.writer(open('bihar_case_cleanup.csv', 'wb'))
        csv_file.writerow(['case_id', 'old_case_type', 'new_case_type',
                           'old_owner_id', 'new_owner_id', 'parent_id',
                           'parent_owner_id'])

        blank_case_type_key = ["all type owner", "care-bihar", "", MOTECH_ID]
        blank_case_ids = [c['id'] for c in
                CommCareCase.view('case/all_cases',
                    startkey=blank_case_type_key,
                    endkey=blank_case_type_key + [{}],
                    reduce=False,
                    include_docs=False
                ).all()]
        task_case_ids = [c['id'] for c in
                CommCareCase.get_all_cases("care-bihar", case_type="task")]

        case_ids = set(blank_case_ids) | set(task_case_ids)
        to_save = []

        for i, doc in enumerate(iter_docs(CommCareCase.get_db(), case_ids)):
            should_save = False
            case = CommCareCase.wrap(doc)

            if case.type != "" or case.type != "task":
                continue

            parent = case.parent
            csv_row = [case._id, case.type, case.type, case.owner_id, case.owner_id]

            if not parent:
                csv_row.extend(['no_parent', 'no_parent'])
            else:
                csv_row.extend([parent._id, parent.owner_id])

            if case.type != 'task':
                if case.user_id != MOTECH_ID:
                    logger.info("{case} was not last submitted by motech".format(case=case._id))
                    continue
                case.type = 'task'
                csv_row[2] = 'task'
                should_save = True

            if parent and parent.owner_id != case.owner_id:
                case.owner_id = parent.owner_id
                csv_row[4] = case.owner_id
                should_save = True

            if should_save:
                to_save.append(case)
                csv_file.writerow(csv_row)

            if len(to_save) > 25:
                CommCareCase.get_db().bulk_save(to_save)
                to_save = []

            if i % 100 == 0:
                logger.info("{current}/{count} cases completed".format(current=i, count=len(case_ids)))

        if to_save:
            CommCareCase.get_db().bulk_save(to_save)
