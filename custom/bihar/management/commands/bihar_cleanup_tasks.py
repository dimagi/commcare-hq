import csv
from datetime import datetime
from optparse import make_option
from django.core.management.base import BaseCommand
from corehq.apps.hqcase.dbaccessors import get_cases_in_domain
from dimagi.utils.decorators.log_exception import log_exception


class Command(BaseCommand):
    """
    Cleans up all duplicate task cases in the system created because
    of bugs in MOTECH
    """
    option_list = BaseCommand.option_list + (
        make_option('--cleanup',
                    action='store_true',
                    dest='cleanup',
                    default=False,
                    help="Clean up (delete) the affected cases."),
    )

    @log_exception()
    def handle(self, *args, **options):
        domain = 'care-bihar'
        root_types = ('cc_bihar_pregnancy', 'cc_bihar_newborn')
        TASK_TYPE = 'task'
        # loop through all mother cases, then all child cases
        # for each case get all associated tasks
        # if any duplicates found, clean up / print them
        with open('bihar-duplicate-tasks.csv', 'wb') as f:
            writer = csv.writer(f, dialect=csv.excel)
            _dump_headings(writer)
            for case_type in root_types:
                for parent_case in get_cases_in_domain(domain, case_type):
                    try:
                        tasks = filter(lambda subcase: subcase.type == TASK_TYPE, parent_case.get_subcases())
                        if tasks:
                            types = [_task_id(t) for t in tasks]
                            unique_types = set(types)
                            if len(unique_types) != len(tasks):
                                for type_being_checked in unique_types:
                                    matching_cases = [t for t in tasks if _task_id(t) == type_being_checked]
                                    if len(matching_cases) > 1:
                                        for row, case in _get_rows(parent_case, matching_cases):
                                            keep = row[-1]
                                            writer.writerow(row)
                                            if options['cleanup'] and not keep:
                                                _purge(case)
                    except Exception, e:
                        print 'error with case %s (%s)' % (parent_case._id, e)


def _task_id(task_case):
    id = getattr(task_case, 'task_id', None)
    if id is None:
        print '%s has no task id' % task_case._id
    return id


def _dump_headings(csv_writer):
    csv_writer.writerow([
        'parent case id',
        'task case id',
        'task id',
        'date created',
        'closed?',
        'keep?',
    ])


def _get_rows(parent, tasklist):
    tasklist = sorted(tasklist, key=lambda case: (not case.closed, case.opened_on))
    for i, task in enumerate(tasklist):
        row = [
            parent._id,
            task._id,
            _task_id(task),
            task.opened_on,
            task.closed,
            i==0,
        ]
        yield (row, task)


def _purge(case):
    case.doc_type = 'CommCareCase-Deleted'
    case.bihar_task_deleted = True
    case.bihar_task_deleted_on = datetime.utcnow()
    case.save()
