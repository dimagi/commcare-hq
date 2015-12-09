import json
from optparse import make_option
import os
from django.core.management import BaseCommand
import sys
from casexml.apps.phone.checksum import Checksum


class Command(BaseCommand):
    """Compare sync logs to see mismatched case ids.
    This is useful for debugging state mismatches

    Can also pass in a hash to see which cases HQ is sending down that mobile has purged.

    Usage:
     ./manage.py sync_log_debugger <synclog1> [synclog2 synclog3]...
        <synclog> is a json file of the synclog you are trying to compare. This
        could also be a folder of synclogs and will compare all of them.

    optional arguments:
    --check <hash>
        removes cases one by one in synclog1 until it matches <hash>
    --index <index>
        if you have more than one file passed in, <index> is the one that --check will be run on
    --depth <depth>
        specify the number of cases to try removing until you find a match in --check
       (it's a N choose X problem so gets very slow after --depth > 1 if you
        have a significant number of cases in the log)
    """
    option_list = BaseCommand.option_list + (
        make_option('--debugger',
                    action='store_true',
                    dest='debugger',
                    default=False,
                    help="Drop into a debugger at the end of running the command for manual queries"),
        make_option('--check',
                    action='store',
                    dest='check_hash',
                    default=None,
                    help=("Run a hash check. Removes cases one by one from the passed-in synclog until "
                          "they hash matches CHECK_HASH")),
        make_option('--index',
                    action='store',
                    dest='index',
                    default=0,
                    help=("if you have more than one file passed in, <index> is the one "
                          "that --check will be run on")),
        make_option('--depth',
                    action='store',
                    dest='depth',
                    default=1,
                    help=("specify the number of cases to try removing until you find a match in --check"
                          "(it's a N choose X problem so gets very slow after --depth > 1 if you"
                          "have a significant number of cases in the log)\n")),
    )

    def handle(self, *args, **options):
        from casexml.apps.phone.models import properly_wrap_sync_log, SyncLog, SimplifiedSyncLog

        if len(args) < 1:
            print(
                "Usage:\n"
                "./manage.py sync_log_debugger <synclog1> [synclog2 synclog3]...\n"
                "    <synclog> is a json file of the synclog you are trying to compare. Passing\n"
                "    in a folder will compare all of the files in that folder.\n"
            )
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
                    elif getattr(wrapped_log, 'migrated_from', None):
                        log_names.append('migrated_from-{}'.format(log_name))
                        logs.append(properly_wrap_sync_log(wrapped_log.to_json()['migrated_from']))

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
                            ', '.join(sorted(case_diff))
                        )

        if options['debugger']:
            union_of_ids = set().union(*[set(log.get_footprint_of_cases_on_phone()) for log in logs])
            intersection_of_ids = set().intersection(*[set(log.get_footprint_of_cases_on_phone()) for log in logs])
            import pdb
            pdb.set_trace()

        if options['check_hash']:
            log_to_check = logs[int(options['index'])]
            result = _brute_force_search(
                log_to_check.case_ids_on_phone, options['check_hash'], depth=int(options['depth'])
            )
            if result:
                print 'check successful - missing ids {}'.format(result)
            else:
                print 'no match found'


def _brute_force_search(case_id_set, expected_hash, diff=None, depth=1):
    # utility for brute force searching for a hash
    diff = diff or set()
    if _get_hash(case_id_set) == expected_hash:
        return diff
    else:
        if depth > 0:
            for id in case_id_set:
                list_to_check = case_id_set - set([id])
                newdiff = diff | set([id])
                result = _brute_force_search(list_to_check, expected_hash, newdiff, depth-1)
                if result:
                    return result
        else:
            return None


def _get_hash(ids):
    return Checksum(list(ids)).hexdigest()
