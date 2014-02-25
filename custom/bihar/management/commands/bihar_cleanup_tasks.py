import csv
from django.core.management.base import BaseCommand
from corehq.apps.hqcase.utils import get_cases_in_domain
from dimagi.utils.decorators.log_exception import log_exception


class Command(BaseCommand):
    """
    Creates the backlog of repeat records that were dropped when bihar repeater
    infrastructure went down.
    """

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
                                        _dump(parent_case, matching_cases, writer)
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

def _dump(parent, tasklist, csv_writer):
    tasklist = sorted(tasklist, key=lambda case: (not case.closed, case.opened_on))
    for i, task in enumerate(tasklist):
        csv_writer.writerow([
            parent._id,
            task._id,
            _task_id(task),
            task.opened_on,
            task.closed,
            i==0,
        ])
