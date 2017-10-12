from __future__ import print_function

from django.core.management import BaseCommand
from django.db import connections

from corehq.apps.hqcase.utils import bulk_update_cases
from corehq.apps.receiverwrapper.exceptions import LocalSubmissionError
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CommCareCaseSQL, CommCareCaseIndexSQL
from corehq.form_processor.utils.sql import fetchall_as_namedtuple

from dimagi.utils.chunked import chunked

import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """See https://docs.google.com/document/d/10DCw7kAeuHIYoWaIpe1Ei5VYMFw3UZcmevyMXW05yyg/edit#"""
    help = "Find duplicate tech_issue_delegat cases and close them"

    def add_arguments(self, parser):
        parser.add_argument(
            'shard',
            help="db shard to query against",
        )
        parser.add_argument(
            'log_file',
            help="File path for log file",
        )

    def handle(self, shard, log_file, **options):
        self.domain = 'icds-cas'
        self.db = shard
        self.case_accessor = CaseAccessors(self.domain)
        failed_updates = []
        with open(log_file, "w") as fh:
            fh.write('--------Successful Form Ids----------\n')
            for delegate_case_ids in chunked(self._get_cases_to_close(), 100):
                case_tupes = [(case_id, {}, True) for case_id in delegate_case_ids]
                try:
                    xform, cases = bulk_update_cases(self.domain, case_tupes, self.__module__)
                    fh.write(xform.form_id + '\n')
                except LocalSubmissionError as e:
                    print('submission error')
                    print(unicode(e))
                    failed_updates.extend(delegate_case_ids)
                except Exception as e:
                    print('unexpected error')
                    print(unicode(e))
                    failed_updates.extend(delegate_case_ids)
            fh.write('--------Failed Cases--------------\n')
            for case_id in failed_updates:
                fh.write(case_id + '\n')
            fh.write('--------Logging Complete--------------\n')
            print('-------------COMPLETE--------------')

    def _get_cases_to_close(self):
        issue_case_ids = get_issue_cases_with_duplicates(self.db, self.domain)
        return get_delegate_case_ids_to_close(self.db, issue_case_ids)


def get_issue_cases_with_duplicates(db, domain):
    case_id_with_dupes_sql = """
        SELECT referenced_id
        FROM {case_index_table} ci JOIN {case_table} c on ci.case_id = c.case_id
        WHERE ci.domain = '{domain}' AND c.type = 'tech_issue_delegate' AND ci.referenced_type = 'tech_issue'
        GROUP BY referenced_id
        HAVING count(*) > 1
    """.format(
        case_index_table=CommCareCaseIndexSQL._meta.db_table,
        case_table=CommCareCaseSQL._meta.db_table,
        domain=domain
    )

    logger.info('Finding tech_issue cases with duplicate delegates')

    with connections[db].cursor() as cursor:
        cursor.execute(case_id_with_dupes_sql)
        rows_with_dupes = fetchall_as_namedtuple(cursor)
        case_ids = {row.referenced_id for row in rows_with_dupes}

    logger.info('Found %s tech_issue cases with duplicate delegates', len(case_ids))
    return case_ids


def get_delegate_case_ids_to_close(db, issue_case_ids):
    case_ids_to_close = """
        SELECT case_id FROM (
          SELECT ci.case_id, row_number()
            OVER (
              PARTITION BY referenced_id
              ORDER BY modified_on DESC
            )
          FROM {case_index_table} ci
            JOIN {case_table} c ON ci.case_id = c.case_id
            JOIN (SELECT UNNEST(ARRAY ['{{case_ids}}']) AS case_id) AS cx ON cx.case_id = ci.referenced_id
          WHERE c.type = 'tech_issue_delegate'
        ) as cases WHERE row_number > 1
        """.format(
        case_index_table=CommCareCaseIndexSQL._meta.db_table,
        case_table=CommCareCaseSQL._meta.db_table,
    )

    logger.info('Finding tech_issue_delegate case IDs to close')
    case_ids = set()
    for chunk in chunked(issue_case_ids, 100):
        with connections[db].cursor() as cursor:
            cursor.execute(case_ids_to_close.format(case_ids="','".join(chunk)))
            rows_with_dupes = fetchall_as_namedtuple(cursor)
            batch = {row.case_id for row in rows_with_dupes}
            logger.info('Found %s tech_issue_delegate case IDs to close', len(batch))
            case_ids.update(batch)

    return case_ids
