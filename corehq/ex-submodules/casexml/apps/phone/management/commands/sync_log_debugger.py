import json
import os
from django.core.management import BaseCommand
import sys
from casexml.apps.phone.models import properly_wrap_sync_log, SyncLog, SimplifiedSyncLog


class Command(BaseCommand):
    """
    lets you download sync logs as json and then compare them.
    useful for checking state issues.
    """

    def handle(self, *args, **options):
        if len(args) < 1:
            print 'Usage: ./manage.py sync_log_debugger <filename1> [<filename2>] [<filename3>]...'
            sys.exit(0)

        logs = []
        log_names = []
        for filename in args:
            if os.path.isdir(filename):
                filenames = [os.path.join(filename, item) for item in sorted(os.listdir(filename))]
            else:
                filenames = [filename]

            for filename in filenames:
                log_name = os.path.basename(filename)
                log_names.append(log_name)
                with open(filename) as f:
                    wrapped_log = properly_wrap_sync_log(json.loads(f.read()))
                    logs.append(wrapped_log)
                    if isinstance(wrapped_log, SyncLog):
                        log_names.append('migrated-{}'.format(log_name))
                        logs.append(SimplifiedSyncLog.from_other_format(wrapped_log))

        print 'state hashes'
        for i in range(len(log_names)):
            print '{} ({}): {}'.format(log_names[i], logs[i]._id, logs[i].get_state_hash())

        print '\ncase diffs'
        for i in range(len(log_names)):
            for j in range(len(log_names)):
                if i != j:
                    case_diff = set(logs[i].get_footprint_of_cases_on_phone()) - \
                        set(logs[j].get_footprint_of_cases_on_phone())
                    if case_diff:
                        print 'cases on {} and not {}: {}'.format(
                            log_names[i],
                            log_names[j],
                            ', '.join(case_diff)
                        )
