import json
import logging
from couchdbkit.exceptions import ResourceConflict, ResourceNotFound
from django.core.management.base import BaseCommand
from restkit import RequestFailed
from casexml.apps.case.cleanup import rebuild_case_from_forms
from casexml.apps.case.const import CASE_ACTION_REBUILD
from casexml.apps.case.models import CommCareCase
from couchlog.models import ExceptionRecord


SEARCH_KEY = 'CASE XFORM MISMATCH'
FULL_SEARCH = '{} AND NOT archived'.format(SEARCH_KEY)


class SearchPaginator(object):
    def __init__(self, database, query, page_size=100):
        self.database = database
        self.query = query
        self.page_size = page_size

        self.bookmark = None

    def next_page(self):
        extra = {}
        if self.bookmark:
            extra['bookmark'] = self.bookmark

        result = ExceptionRecord.get_db().search(
            'couchlog/_search/search',
            handler='_design',
            q=self.query,
            include_docs=True,
            limit=self.page_size,
            **extra
        )

        try:
            result.fetch()
            self.bookmark = result._result_cache.get('bookmark')
            return result
        except RequestFailed:
            # ignore for now
            return []


def row_to_record(row):
    doc = ExceptionRecord.wrap(row["doc"])
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


def dump_logs_to_file(filename):
    print 'Writing logs to file'
    paginator = SearchPaginator(ExceptionRecord.get_db(), FULL_SEARCH)

    records_written = 0
    try:
        with open(filename, 'w') as log_file:
            while True:
                page = paginator.next_page()
                if not page:
                    return

                for row in page:
                    record = row_to_record(row)
                    if record['exception']['archived']:
                        continue
                    if 'case_id' not in record and SEARCH_KEY not in record['exception']['message']:
                        # search results are no longer relevant
                        return

                    log_file.write('{}\n'.format(json.dumps(record)))
                    records_written += 1
                    if records_written % 100 == 0:
                        print '{} records written to file'.format(records_written)
    finally:
        print '{} records written to file'.format(records_written)


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
        dump_logs_to_file(filename)

        seen_cases = set()
        cases_rebuilt = set()
        with open(filename, 'r') as file:
            while True:
                line = file.readline()
                if not line:
                    return

                print 'Processing record {}'.format(count)
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
                        cases_rebuilt.add(case_id)
                        rebuild_case_from_forms(case_id)
                        print 'rebuilt case {}'.format(case_id)
                    archive_exception(exception)
                except Exception, e:
                    logging.exception("couldn't rebuild case {id}. {msg}".format(id=case_id, msg=str(e)))
                finally:
                    count += 1

        print "Cases rebuilt: {}".format(cases_rebuilt)
