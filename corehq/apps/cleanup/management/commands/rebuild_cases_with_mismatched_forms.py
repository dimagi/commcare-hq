import logging
from optparse import make_option
from django.core.management.base import BaseCommand, LabelCommand
from casexml.apps.case.cleanup import rebuild_case
from couchlog.models import ExceptionRecord
from dimagi.utils.couch.pagination import LucenePaginator
from django.conf import settings

SEARCH_VIEW_NAME = getattr(settings, "COUCHLOG_LUCENE_VIEW", "couchlog/search")


def get_records_to_process(search_key, batch_size):
    def wrapper(row):
        id = row["id"]
        doc = ExceptionRecord.get(id)
        domain = doc.domain if hasattr(doc, "domain") else ""
        domain, case_id = domain.split(',')
        return {
            'domain': domain,
            'case_id': case_id,
            'exception': doc
        }

    search_key = "%s AND NOT archived" % search_key

    paginator = LucenePaginator(SEARCH_VIEW_NAME, wrapper, database=ExceptionRecord.get_db())
    return paginator.get_results(search_key, batch_size, 0)


class Command(BaseCommand):
    help = ('Rebuild cases that have been identified to have mismatched forms and actions.'
            'See http://manage.dimagi.com/default.asp?158779 for details.')

    option_list = LabelCommand.option_list + (
        make_option(
            '--limit',
            action='store',
            dest='limit',
            default=1000,
            help="Only reprocess this many cases."),
        make_option(
            '--batch-size',
            action='store',
            dest='batch',
            default=100,
            help="Size of batches to process"),
    )

    def handle(self, *args, **options):
        count = 0
        limit = options['limit']
        batch = options['batch']
        while True:
            total, records = get_records_to_process('CASE XFORM MISMATCH', batch)
            for record in records:
                case_id = record['case_id']
                try:
                    rebuild_case(case_id)
                    record['exception'].archive('system')
                    if count % 100 == 0:
                        print 'rebuilt %s/%s cases' % (count, total)
                except Exception, e:
                    logging.exception("couldn't rebuild case {id}. {msg}".format(id=case_id, msg=str(e)))
                finally:
                    count += 1
                    if count > limit:
                        return
