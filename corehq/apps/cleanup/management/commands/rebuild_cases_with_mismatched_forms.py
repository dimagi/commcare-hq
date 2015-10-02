import json
import logging
from couchdbkit.exceptions import ResourceConflict, ResourceNotFound
from django.core.management.base import BaseCommand
from casexml.apps.case.cleanup import rebuild_case
from casexml.apps.case.const import CASE_ACTION_REBUILD
from casexml.apps.case.models import CommCareCase
from couchlog.models import ExceptionRecord
from dimagi.utils.couch.pagination import LucenePaginator
from django.conf import settings

SEARCH_KEY = 'CASE XFORM MISMATCH'
SEARCH_VIEW_NAME = getattr(settings, "COUCHLOG_LUCENE_VIEW", "couchlog/search")


def get_records_to_process(search_key, limit, skip=0):
    def wrapper(row):
        id = row["id"]
        doc = ExceptionRecord.get(id)
        domain = doc.domain if hasattr(doc, "domain") else ""
        try:
            domain, case_id = domain.split(',')
        except ValueError:
            return {'exception': doc.to_json()}
        return {
            'domain': domain,
            'case_id': case_id,
            'exception': doc.to_json()
        }

    search_key = "%s AND NOT archived" % search_key

    paginator = LucenePaginator(SEARCH_VIEW_NAME, wrapper, database=ExceptionRecord.get_db())
    return paginator.get_results(search_key, limit, skip)


def dump_logs_to_file(filename):
    def _get_records(skip):
        total, records = get_records_to_process(SEARCH_KEY, 100, skip)
        return total, list(records)

    records_written = 0
    with open(filename, 'w') as file:
        total, records = _get_records(0)
        print "{} records found".format(total)
        while records:
            records_written += len(records)
            for record in records:
                file.write('{}\n'.format(json.dumps(record)))
            print '{} of {} records writen to file'.format(records_written, total)
            total, records = _get_records(records_written)
    return total


def archive_exception(exception):
    try:
        exception.archive('system')
    except ResourceConflict:
        pass


def should_rebuild(case_id):
    try:
        case = CommCareCase.get(case_id)
        return case.actions[-1].action_type != CASE_ACTION_REBUILD
    except ResourceNotFound:
        return True


class Command(BaseCommand):
    help = ('Rebuild cases that have been identified to have mismatched forms and actions.'
            'See http://manage.dimagi.com/default.asp?158779 for details.')

    def handle(self, *args, **options):
        count = 1
        filename = 'cases_with_mismatched_forms.log'
        total = dump_logs_to_file(filename)

        seen_cases = set()
        with open(filename, 'r') as file:
            while True:
                line = file.readline()
                if not line:
                    return

                print 'Processing record {} of {}'.format(count, total)
                record = json.loads(line)
                exception = ExceptionRecord.wrap(record['exception'])
                case_id = record.get('case_id', None)
                if not case_id or case_id in seen_cases:
                    count += 1
                    archive_exception(exception)
                    continue

                try:
                    seen_cases.add(case_id)
                    if should_rebuild(case_id):
                        rebuild_case(case_id)
                        print 'rebuilt case {}'.format(case_id)
                    archive_exception(exception)
                except Exception, e:
                    logging.exception("couldn't rebuild case {id}. {msg}".format(id=case_id, msg=str(e)))
                finally:
                    count += 1
